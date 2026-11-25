#!/usr/bin/env python3
"""見ておきたいInstagramアカウントのリールを取り、再生数の多い順に trends_auto.json に書く。

trend_accounts.json の accounts に {"username": "xxx", "genre": "AI系"} を並べる。
使うのは Instagram の公式の仕組み（Business Discovery）。相手がビジネス／クリエイターアカウントの時だけ取れる。

必要な環境変数
  META_IG_TOKEN または META_ACCESS_TOKEN
    Instagramを読む権限（instagram_basic・instagram_manage_insights・pages_read_engagement）が付いたトークン。
    自社のInstagramビジネスアカウント（とそのFacebookページ）が、トークンの持ち主に割り当てられていること。
任意
  META_IG_USER_ID   自社のInstagramビジネスアカウントのID。空なら自動で探す
  IG_TEST           1 にすると、設定を書き換えずに「instagram」公式アカウントで読めるかだけ試す
失敗してもエラー終了しない（広告の数字の更新を止めないため）。
"""
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF, OUT = os.path.join(ROOT, 'trend_accounts.json'), os.path.join(ROOT, 'trends_auto.json')
JST = datetime.timezone(datetime.timedelta(hours=9))
TOKEN = (os.environ.get('META_IG_TOKEN') or os.environ.get('META_ACCESS_TOKEN') or '').strip()


def api(path, params):
    ver = os.environ.get('META_API_VERSION', '').strip()
    url = 'https://graph.facebook.com/' + (ver + '/' if ver else '') + path + '?' + urllib.parse.urlencode(dict(params, access_token=TOKEN))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        try:
            err = json.loads(body).get('error', {})
            return None, f"{err.get('message', body[:200])}（code {err.get('code')}）"
        except Exception:
            return None, body[:200]
    except Exception as e:
        return None, str(e)


def my_ig_id():
    if os.environ.get('META_IG_USER_ID', '').strip():
        return os.environ['META_IG_USER_ID'].strip()
    d, err = api('me/accounts', {'fields': 'name,instagram_business_account{id,username}', 'limit': 100})
    if err:
        print('自社のInstagramアカウントを探せませんでした:', err)
        return None
    pages = d.get('data', [])
    igs = [p['instagram_business_account'] for p in pages if p.get('instagram_business_account')]
    print(f'トークンで見えるFacebookページ {len(pages)}個、うちInstagramがつながっているもの {len(igs)}個')
    if not igs:
        print('→ Instagramビジネスアカウントがつながったページが、このトークンに割り当てられていません。')
        return None
    print('自社のInstagram:', igs[0].get('username', ''))
    return igs[0]['id']


def fetch(ig_id, username):
    fields = ('business_discovery.username(%s){username,name,followers_count,media_count,'
              'media.limit(60){id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count,view_count}}') % username
    d, err = api(ig_id, {'fields': fields})
    if err and 'view_count' in err:  # 再生数の項目が使えない版の時は外して取り直す
        d, err = api(ig_id, {'fields': fields.replace(',view_count', '')})
    return (d or {}).get('business_discovery'), err


def hashtag_test(ig_id):
    """ハッシュタグ検索が今のトークンで使えるかだけ試す（何も書き換えない）。"""
    for tag in ('ai動画', 'もしも'):
        d, err = api('ig_hashtag_search', {'user_id': ig_id, 'q': tag})
        if err or not (d or {}).get('data'):
            print(f'  #{tag}: 検索できませんでした（{err}）'); continue
        hid = d['data'][0]['id']
        m, err = api(f'{hid}/top_media', {'user_id': ig_id, 'limit': 50, 'fields': 'id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count'})
        if err:
            print(f'  #{tag}: 人気の投稿を取れませんでした（{err}）'); continue
        rows = m.get('data', [])
        vids = [r for r in rows if r.get('media_type') == 'VIDEO' or r.get('media_product_type') == 'REELS']
        likes = sorted([r.get('like_count') or 0 for r in vids], reverse=True)[:5]
        print(f'  #{tag}: 人気の投稿 {len(rows)}件・うち動画 {len(vids)}件・いいね上位 {likes}・種類 {sorted({str(r.get("media_product_type")) for r in rows})}')


def main():
    if not TOKEN:
        print('トークンがありません。'); return
    conf = json.load(open(CONF, encoding='utf-8')) if os.path.exists(CONF) else {}
    test = os.environ.get('IG_TEST') in ('1', 'hashtag')
    accounts = [{'username': 'instagram', 'genre': 'テスト'}] if test else conf.get('accounts') or []
    if not accounts:
        print('trend_accounts.json に見ておきたいアカウントがまだ入っていません。'); return
    ig_id = my_ig_id()
    if not ig_id:
        return
    if os.environ.get('IG_TEST') == 'hashtag':
        hashtag_test(ig_id); return
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(conf.get('days', 30)))
    items, ok = [], 0
    min_ratio = float(conf.get('minRatio') or 0)  # 再生数がフォロワー数の何倍以上のリールだけ残すか
    for a in accounts:
        u = str(a.get('username', '')).strip().lstrip('@')
        if not u:
            continue
        bd, err = fetch(ig_id, u)
        if not bd:
            print(f'  @{u}: 取れませんでした（{err}）'); continue
        ok += 1
        rows = []
        for m in (bd.get('media') or {}).get('data', []):
            if m.get('media_product_type') != 'REELS' and m.get('media_type') != 'VIDEO':
                continue
            try:
                ts = datetime.datetime.strptime(m['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
            except Exception:
                continue
            if ts < since:
                continue
            fol = bd.get('followers_count') or 0
            views = m.get('view_count')
            rows.append({
                'url': m.get('permalink'), 'genre': [a.get('genre') or 'その他'], 'kind': 'リール・ショート動画',
                'memo': ' '.join(str(m.get('caption') or '').split())[:90], 'username': bd.get('username', u), 'followers': fol,
                'views': views, 'likes': m.get('like_count'), 'comments': m.get('comments_count'),
                'ratio': round(views / fol, 2) if views and fol else None,
                'postedAt': ts.astimezone(JST).replace(microsecond=0).isoformat(),
            })
        hit = [r for r in rows if (r['ratio'] or 0) >= min_ratio] if min_ratio else rows
        hit.sort(key=lambda r: -((r['views'] or 0) or (r['likes'] or 0)))
        best = max([r['ratio'] or 0 for r in rows], default=0)
        print(f'  @{u}: フォロワー {bd.get("followers_count")}・直近{conf.get("days", 30)}日のリール {len(rows)}本・最大 {best}倍・基準（{min_ratio}倍以上）を超えた {len(hit)}本')
        items += hit[:int(conf.get('perAccount', 5))]
    if test:
        print('テスト終了。読めたアカウント', ok, '／ 取れたリール', len(items), '／ 再生数あり', sum(1 for r in items if r['views'] is not None)); return
    if not ok:
        print('1つも読めなかったので、trends_auto.json は書き換えていません。'); return
    items = [r for r in items if r['url']]
    items.sort(key=lambda r: -((r['views'] or 0) or (r['likes'] or 0)))
    out = {'rule': f'直近{conf.get("days", 30)}日・再生数がフォロワー数の{min_ratio:g}倍以上' if min_ratio else f'直近{conf.get("days", 30)}日', 'updatedAt': datetime.datetime.now(JST).replace(microsecond=0).isoformat(), 'items': items[:int(conf.get('keep', 40))]}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.write('\n')
    print(f'trends_auto.json を書き換えました：{len(out["items"])}本（{ok}アカウント）')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:  # ここで失敗しても全体は止めない
        print('Instagramの取得で予期しないエラー:', e)
    sys.exit(0)
