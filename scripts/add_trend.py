#!/usr/bin/env python3
"""trends.json に1件足す。値は環境変数で受け取る（TREND_URL / TREND_GENRE / TREND_KIND / TREND_MEMO / TREND_BY）。"""
import datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'trends.json')
JST = datetime.timezone(datetime.timedelta(hours=9))

url = os.environ.get('TREND_URL', '').strip()
if not re.match(r'^https://[^\s<>"\']+$', url):
    sys.exit('URLは https:// から始まる形で入れてください。')
url = re.sub(r'[?&](igsh|igshid|utm_[a-z]+|si|fbclid)=[^&#]*', '', url).rstrip('?&')  # 共有用の余計な印を落とす
items = json.load(open(PATH, encoding='utf-8')) if os.path.exists(PATH) else []
key = lambda u: u.split('?')[0].rstrip('/') if 'facebook.com/ads/library' not in u else u
if any(key(t.get('url', '')) == key(url) for t in items):
    print('同じURLがすでに入っています。何も足していません。')
    sys.exit(0)
genre = [g.strip() for g in re.split(r'[,、]', os.environ.get('TREND_GENRE', '')) if g.strip()]
items.append({
    'id': 't' + datetime.datetime.now(JST).strftime('%Y%m%d%H%M%S'),
    'url': url, 'genre': genre, 'kind': os.environ.get('TREND_KIND', '').strip(),
    'memo': os.environ.get('TREND_MEMO', '').strip()[:500],
    'addedAt': datetime.datetime.now(JST).replace(microsecond=0).isoformat(),
    'addedBy': os.environ.get('TREND_BY', '').strip()[:40],
})
with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=1)
    f.write('\n')
print(f'足しました：{url}（合計 {len(items)}件）')
