#!/usr/bin/env python3
"""Meta広告の数字を取って data.json を書き換える。

必要な環境変数
  META_ACCESS_TOKEN    Metaのアクセストークン（ads_read）。GitHubのSecretsに入れる
  META_AD_ACCOUNT_ID   広告アカウントID（act_ は付けても付けなくてもよい）。複数ある時はカンマ区切り（例 111,222）
任意
  META_API_VERSION     例 v24.0。空ならMeta側の既定の版を使う
  META_LISTIN_ACTION   リストインとして数えるアクション名を1つに固定したい時
  DAYS                 さかのぼる日数（既定60）

やること
  1. 直近DAYS日の、広告ごと・日ごとの数字を取る
  2. 広告のクリエイティブ画像を creatives/ に保存し、リンク先からLPを割り出す
  3. data.json の campaigns・creatives を入れ替える（lps・目標の数字は残す）
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data.json')
CR_DIR = os.path.join(ROOT, 'creatives')
JST = datetime.timezone(datetime.timedelta(hours=9))

# リストインとして数える候補。上にあるものを優先し、数字が1件でもある最初の1つだけを使う（足し合わせると二重に数えるため）
LISTIN_CANDIDATES = [
    'offsite_conversion.fb_pixel_complete_registration',
    'complete_registration',
    'offsite_conversion.fb_pixel_lead',
    'lead',
    'onsite_conversion.lead_grouped',
]


def api(path, params, soft=False):
    """Graph APIを呼ぶ。ページ送りをたどって全件返す。"""
    ver = os.environ.get('META_API_VERSION', '').strip()
    base = 'https://graph.facebook.com/' + (ver + '/' if ver else '')
    params = dict(params, access_token=os.environ['META_ACCESS_TOKEN'])
    url = base + path + '?' + urllib.parse.urlencode(params)
    out = []
    while url:
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            try:
                msg = json.loads(body).get('error', {}).get('message', body)
            except Exception:
                msg = body[:300]
            if soft:
                print(f'  （読めませんでした {path}: {msg}）')
                return None
            sys.exit(f'Metaからエラーが返りました（{e.code}）: {msg}')
        if 'data' not in d or not isinstance(d['data'], list):
            return d
        out += d['data']
        url = d.get('paging', {}).get('next')
    return out


def download(url, dest):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            b = r.read()
        if len(b) < 500:
            return False
        with open(dest, 'wb') as f:
            f.write(b)
        return True
    except Exception as e:
        print(f'  画像を保存できませんでした: {os.path.basename(dest)} ({e})')
        return False


def link_of(creative):
    """クリエイティブのリンク先URLを探す。"""
    spec = creative.get('object_story_spec') or {}
    for k in ('link_data', 'video_data', 'template_data'):
        d = spec.get(k) or {}
        if d.get('link'):
            return d['link']
        link = ((d.get('call_to_action') or {}).get('value') or {}).get('link')
        if link:
            return link
    for u in (creative.get('asset_feed_spec') or {}).get('link_urls') or []:
        if u.get('website_url'):
            return u['website_url']
    return creative.get('link_url') or ''


def is_video(creative):
    spec = creative.get('object_story_spec') or {}
    if creative.get('video_id') or spec.get('video_data'):
        return True
    return bool((creative.get('asset_feed_spec') or {}).get('videos'))


def lp_id_from(url):
    m = re.search(r'/p/([A-Za-z0-9]{6,})', url or '')
    return m.group(1) if m else None


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def build(rows, ads, old):
    """APIの結果から data.json の中身を組み立てる。"""
    # リストインに使うアクションを決める
    totals = {}
    for r in rows:
        for a in r.get('actions') or []:
            totals[a['action_type']] = totals.get(a['action_type'], 0) + num(a.get('value'))
    forced = os.environ.get('META_LISTIN_ACTION', '').strip()
    listin_type = forced or next((t for t in LISTIN_CANDIDATES if totals.get(t, 0) > 0), LISTIN_CANDIDATES[0])
    print('アクションの合計（多い順）:')
    for t, v in sorted(totals.items(), key=lambda x: -x[1])[:25]:
        print(f'  {t}: {int(v)}')
    print(f'リストインとして数えるアクション: {listin_type}')

    lps = list(old.get('lps') or [])
    known = {l['id'] for l in lps}
    campaigns, creatives = {}, {}
    for r in rows:
        ad_id = r['ad_id']
        campaigns[r['campaign_id']] = {'id': r['campaign_id'], 'name': r.get('campaign_name') or r['campaign_id'], 'account': r.get('account_name') or ''}
        c = creatives.get(ad_id)
        if c is None:
            cr = (ads.get(ad_id) or {}).get('creative') or {}
            link = link_of(cr)
            lp_id = lp_id_from(link)
            if lp_id and lp_id not in known:
                lps.append({'id': lp_id, 'name': 'LP ' + lp_id, 'group': '未分類', 'funnel': 'Metaの広告リンクから追加',
                            'url': link.split('?')[0], 'thumbUrl': None, 'source': 'UTAGE', 'stage': '入口', 'entry': True})
                known.add(lp_id)
            if not lp_id:
                lp_id = 'unknown'
                if lp_id not in known:
                    lps.append({'id': 'unknown', 'name': 'リンク先がUTAGE以外・不明', 'group': '未分類', 'funnel': '',
                                'url': link.split('?')[0] if link else '', 'thumbUrl': None, 'source': '', 'stage': '入口', 'entry': True})
                    known.add(lp_id)
            c = creatives[ad_id] = {
                'id': ad_id, 'name': r.get('ad_name') or ad_id, 'adset': r.get('adset_name') or '', 'account': r.get('account_name') or '', 'format': '動画' if is_video(cr) else '画像',
                'campaignId': r['campaign_id'], 'lpId': lp_id, 'imageUrl': None, 'videoUrl': None, 'copy': '',
                '_img': cr.get('image_url') or cr.get('thumbnail_url'), 'daily': [],
            }
        acts = {a['action_type']: num(a.get('value')) for a in r.get('actions') or []}
        c['daily'].append({
            'date': r['date_start'], 'spend': round(num(r.get('spend'))), 'imp': int(num(r.get('impressions'))),
            'click': int(num(r.get('inline_link_clicks'))), 'lpview': int(acts.get('landing_page_view', 0)),
            'listin': int(acts.get(listin_type, 0)),
        })
    for c in creatives.values():
        c['daily'].sort(key=lambda d: d['date'])
    out = {k: v for k, v in old.items() if k not in ('sample', 'campaigns', 'creatives', 'lps', 'updatedAt', 'listinSource', 'tokenExpiresAt')}
    return {
        'updatedAt': datetime.datetime.now(JST).replace(microsecond=0).isoformat(),
        'listinSource': 'Meta: ' + listin_type,
        **out,
        'campaigns': sorted(campaigns.values(), key=lambda x: x['name']),
        'lps': lps,
        'creatives': sorted(creatives.values(), key=lambda x: x['name']),
    }


def save_images(data):
    os.makedirs(CR_DIR, exist_ok=True)
    for c in data['creatives']:
        url = c.pop('_img', None)
        dest = os.path.join(CR_DIR, f"meta_{c['id']}.jpg")
        if os.path.exists(dest) or (url and download(url, dest)):
            c['imageUrl'] = f"creatives/meta_{c['id']}.jpg"


def main():
    for k in ('META_ACCESS_TOKEN', 'META_AD_ACCOUNT_ID'):
        if not os.environ.get(k, '').strip():
            sys.exit(f'{k} が入っていません。GitHubの Settings → Secrets and variables → Actions に入れてください。')
    acts = ['act_' + re.sub(r'^act_', '', a.strip()) for a in re.split(r'[,\s]+', os.environ['META_AD_ACCOUNT_ID'].strip()) if a.strip()]
    acts = list(dict.fromkeys(acts))  # 同じIDが2回入っていても1回だけ取る
    days = int(os.environ.get('DAYS') or 60)
    today = datetime.datetime.now(JST).date()
    rng = {'since': (today - datetime.timedelta(days=days - 1)).isoformat(), 'until': today.isoformat()}

    rows = []
    for n, act in enumerate(acts, 1):
        got = api(f'{act}/insights', {
            'level': 'ad', 'time_increment': 1, 'limit': 500, 'time_range': json.dumps(rng),
            'fields': 'account_name,ad_id,ad_name,adset_name,campaign_id,campaign_name,spend,impressions,inline_link_clicks,actions',
        })
        if got:
            name = got[0].get('account_name', '')
        else:
            info = api(act, {'fields': 'name'}, soft=True)
            name = (info.get('name', '') + '・この期間の配信なし') if info else '読めません。トークンにこのアカウントの権限が無い可能性'
        print(f'アカウント{n}（{name}）：{len(got)}行（広告×日）')
        rows += got
    print(f'{rng["since"]}〜{rng["until"]}：合計 {len(rows)}行')
    if not rows:
        sys.exit('この期間に配信した広告がありません。data.json は書き換えていません。')

    ads = {}
    ids = sorted({r['ad_id'] for r in rows})
    fields = ('creative.thumbnail_width(900).thumbnail_height(900)'
              '{thumbnail_url,image_url,video_id,object_story_spec,asset_feed_spec,link_url}')
    for i in range(0, len(ids), 50):
        res = api('', {'ids': ','.join(ids[i:i + 50]), 'fields': fields})
        ads.update(res if isinstance(res, dict) else {})

    old = json.load(open(DATA, encoding='utf-8')) if os.path.exists(DATA) else {}
    data = build(rows, ads, old)
    # トークンの期限（分かる時だけ）。0 は期限なし
    info = api('debug_token', {'input_token': os.environ['META_ACCESS_TOKEN']}, soft=True)
    exp = ((info or {}).get('data') or {}).get('expires_at')
    if exp:
        data['tokenExpiresAt'] = datetime.datetime.fromtimestamp(exp, JST).date().isoformat()
        print('トークンの期限:', data['tokenExpiresAt'])
    save_images(data)
    with open(DATA, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'data.json を書き換えました：広告 {len(data["creatives"])}本・キャンペーン {len(data["campaigns"])}個・LP {len(data["lps"])}本')


if __name__ == '__main__':
    main()
