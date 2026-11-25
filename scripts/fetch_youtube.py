#!/usr/bin/env python3
"""YouTubeショートを言葉で探し、伸びている動画を trends_youtube.json に書く（動画単位のトレンド）。

trend_queries.json の queries に {"q": "探す言葉", "genre": "ジャンル"} を並べる。
残す基準：直近 days 日以内・長さ maxSeconds 秒以内・再生数 minViews 以上・再生数がチャンネル登録者数の minRatio 倍以上。
必要な環境変数：YOUTUBE_API_KEY（Google Cloud の YouTube Data API v3 のキー。無料枠で足りる）
1日1回だけ動かす（検索1回で無料枠を100使う。1日の枠は10,000）。失敗してもエラー終了しない。
"""
import datetime, json, os, re, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF, OUT = os.path.join(ROOT, 'trend_queries.json'), os.path.join(ROOT, 'trends_youtube.json')
JST = datetime.timezone(datetime.timedelta(hours=9))
KEY = os.environ.get('YOUTUBE_API_KEY', '').strip()


def api(path, params):
    url = 'https://www.googleapis.com/youtube/v3/' + path + '?' + urllib.parse.urlencode(dict(params, key=KEY))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        try:
            return None, json.loads(body).get('error', {}).get('message', body[:200])
        except Exception:
            return None, body[:200]
    except Exception as e:
        return None, str(e)


def seconds(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', iso or '')
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else None


def main():
    if not KEY:
        print('YOUTUBE_API_KEY が入っていないので、YouTubeの収集は飛ばします。'); return
    conf = json.load(open(CONF, encoding='utf-8'))
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(conf.get('days', 180)))).strftime('%Y-%m-%dT%H:%M:%SZ')
    found = {}  # video id -> genre
    for q in conf.get('queries', []):
        d, err = api('search', {'part': 'id', 'q': q['q'], 'type': 'video', 'videoDuration': 'short', 'order': 'viewCount',
                                'publishedAfter': after, 'regionCode': 'JP', 'relevanceLanguage': 'ja', 'maxResults': 25})
        if err:
            print(f'  「{q["q"]}」: 探せませんでした（{err}）'); continue
        ids = [i['id']['videoId'] for i in d.get('items', []) if i.get('id', {}).get('videoId')]
        for v in ids:
            found.setdefault(v, (q.get('genre') or 'その他', q['q'], q))
        print(f'  「{q["q"]}」: {len(ids)}本')
    if not found:
        print('1本も見つからなかったので、trends_youtube.json は書き換えていません。'); return
    vids, ids = {}, list(found)
    for i in range(0, len(ids), 50):
        d, err = api('videos', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(ids[i:i + 50])})
        if d:
            vids.update({v['id']: v for v in d.get('items', [])})
    chans, cids = {}, sorted({v['snippet']['channelId'] for v in vids.values()})
    for i in range(0, len(cids), 50):
        d, err = api('channels', {'part': 'statistics,snippet', 'id': ','.join(cids[i:i + 50])})
        if d:
            chans.update({c['id']: c for c in d.get('items', [])})
    min_ratio, min_views, max_sec = float(conf.get('minRatio') or 0), int(conf.get('minViews') or 0), int(conf.get('maxSeconds') or 90)
    by_q = {}
    for vid, v in vids.items():
        sn, st = v['snippet'], v.get('statistics', {})
        sec, views = seconds(v.get('contentDetails', {}).get('duration')), int(st.get('viewCount') or 0)
        ch = chans.get(sn['channelId'], {})
        subs = int((ch.get('statistics') or {}).get('subscriberCount') or 0)
        ratio = round(views / subs, 2) if subs else None
        genre, q, qc = found[vid]
        mv, mr = int(qc.get('minViews', min_views)), float(qc.get('minRatio', min_ratio))  # 検索語ごとに基準を変えられる
        if sec is None or sec > max_sec or views < mv or (mr and (ratio or 0) < mr):
            continue
        if not re.search(r'[぀-ヿ一-鿿]', sn.get('title', '') + (ch.get('snippet') or {}).get('title', '')):
            continue  # 日本語のものだけ
        by_q.setdefault(q, []).append({
            'url': f'https://www.youtube.com/shorts/{vid}', 'genre': [genre], 'kind': 'リール・ショート動画', 'memo': sn.get('title', '')[:90],
            'username': sn.get('channelTitle', ''), 'followers': subs, 'views': views, 'likes': int(st.get('likeCount') or 0),
            'comments': int(st.get('commentCount') or 0), 'ratio': ratio, 'seconds': sec, 'postedAt': sn.get('publishedAt'), 'site': 'YouTube', 'query': q,
        })
    items = []
    for q, rows in by_q.items():
        rows.sort(key=lambda r: -r['views'])
        items += rows[:int(conf.get('perQuery', 8))]
    items.sort(key=lambda r: -r['views'])
    rule = f'直近{conf.get("days", 180)}日・{max_sec}秒以内・{min_views:,}再生以上' + (f'・再生数が登録者数の{min_ratio:g}倍以上' if min_ratio else '') + '（本数の少ないジャンルは基準をゆるめています）'
    out = {'rule': rule, 'updatedAt': datetime.datetime.now(JST).replace(microsecond=0).isoformat(), 'items': items[:int(conf.get('keep', 60))]}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.write('\n')
    print(f'trends_youtube.json を書き換えました：{len(out["items"])}本（候補 {len(vids)}本から）')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('YouTubeの取得で予期しないエラー:', e)
    sys.exit(0)
