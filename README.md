# Harukaze広告ツール

広告の数字（リストイン数・広告費・1リストインの費用）を、クリエイティブ別・LP別に見る画面。
公開リポジトリ（2026-11-24 本人決定）。URLを知っていれば誰でも見られるので、`data.json` に入れた数字はそのまま外から見える。

- 画面：https://koya-ship-it.github.io/harukaze-ads-tool/
- 数字：https://github.com/koya-ship-it/harukaze-ads-tool/blob/main/data.json

## 中身

| ファイル | 役割 |
|---|---|
| `index.html` | 画面。開くたびに同じ場所の `data.json` を読む |
| `data.json` | **数字の正本。Grok Botが毎日書き換えるのはこのファイルだけ** |
| `sample_data.json` | 形の見本（触らない） |
| `データの形_GrokBot向け.md` | 各項目の意味・取得元・未決事項 |

## Grok Botが毎日やること

1. `data.json` を開く。
2. 各広告（`creatives[]`）の `daily` に、その日の1行 `{date, spend, imp, click, lpview, listin}` を足す。同じ日付の行があれば上書きする。数字が無い項目は `0`。
3. 新しい広告・LP・キャンペーンが出ていたら `creatives`・`lps`・`campaigns` に足す。
4. `updatedAt` を今の日本時間にする（例 `2026-11-24T09:00:00+09:00`）。
5. 本物の数字を入れ始めたら、先頭の `"sample": true` を消す（画面の「サンプルデータ」の表示が消える）。
6. `data.json` だけをコミットする。`index.html` は書き換えない。

クリック率・登録率・1リストインの費用・好調／停止候補は画面側で計算するので入れない。

## 今の状態（2026-11-24）

- `data.json` の中身は見本の数字。本物はまだ入っていない。
- 見る場所は上の「画面」のURL。`data.json` を書き換えてコミットすると、数分で画面に出る。
- 未決事項は `データの形_GrokBot向け.md` の「まだ決まっていないこと」を参照。
