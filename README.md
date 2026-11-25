# Harukaze広告ツール

広告の数字（リストイン数・広告費・1リストインの費用）を、クリエイティブ別・LP別に見る画面。
公開リポジトリ（2026-11-24 本人決定）。URLを知っていれば誰でも見られるので、`data.json` に入れた数字はそのまま外から見える。

- 画面：https://koya-ship-it.github.io/harukaze-ads-tool/
- 数字：https://github.com/koya-ship-it/harukaze-ads-tool/blob/main/data.json

## 画面の構成

左のメニューは「導線まとめ」と、その下に導線（プロジェクト）が並ぶ。導線を押すと、その導線だけのダッシュボード・クリエイティブ・LPが見られる。
導線とキャンペーン・LPの対応は `data.json` の `projects` に持つ（`campaignIds`＝Metaのキャンペーン、`lpGroups`＝`lps` の `group`）。`projects` に無いキャンペーンは、自動で1キャンペーン＝1導線として出る。名前を付けたい時は `projects` に足す。自動更新では消えない。

## トレンド（伸びているクリエイティブの置き場）

左のメニューの「トレンド」に、`trends.json` に入っているURLが新しい順に並ぶ。Instagramのリール・TikTok・YouTubeは公式の埋め込みでその場で見られ、広告ライブラリなど埋め込めないものはリンクで並ぶ。ジャンル・種類・言葉で絞れる。

自動で集まる分：`trend_accounts.json` の `accounts` に `{"username": "アカウント名", "genre": "AI系"}` を並べると、更新のたびにそのアカウントの直近30日のリールを取り、再生数の多い順に `trends_auto.json` へ書く（`scripts/fetch_ig.py`）。相手がビジネス／クリエイターアカウントの時だけ取れる。Instagramを読む権限つきのトークンが要る（`META_ACCESS_TOKEN` に権限を足すか、別に `META_IG_TOKEN` を入れる）。読めるかは Actions の「Instagramを読めるか試す」で確かめられる。

手で足す時（どれでもよい）
- 画面の「＋ URLを足す」→ GitHubの「トレンドを足す」→ Run workflow → URL・ジャンル・種類・メモを入れて実行。1〜2分で並ぶ。
- Grok BotやAIが `trends.json` に直接足す。形は `{id, url, genre: [..], kind, memo, addedAt, addedBy}`。
- 消す・直す時は `trends.json` を編集する。

## 中身

| ファイル | 役割 |
|---|---|
| `index.html` | 画面。開くたびに同じ場所の `data.json` を読む |
| `data.json` | **数字の正本。Grok Botが毎日書き換えるのはこのファイルだけ** |
| `sample_data.json` | 形の見本（触らない） |
| `creatives/` | 広告クリエイティブの画像・動画。`data.json` の `imageUrl` / `videoUrl` に `creatives/ファイル名` と書くと画面に出る |
| `データの形_GrokBot向け.md` | 各項目の意味・取得元・未決事項 |

## 毎日の自動更新（Metaから直接）

`.github/workflows/update.yml` が8:30から3時間おき（日本時間・23:30まで）に `scripts/fetch_meta.py` を動かし、Metaから直近60日の数字と広告画像を取って `data.json` と `creatives/` を書き換える。手で今すぐ動かす時は、GitHubの Actions →「Metaから数字を取る」→ Run workflow。

### 最初に1回だけ入れるもの（Settings → Secrets and variables → Actions → New repository secret）

| 名前 | 中身 |
|---|---|
| `META_ACCESS_TOKEN` | Metaのアクセストークン（`ads_read` の権限つき）。チャットやファイルには書かない |
| `META_AD_ACCOUNT_ID` | 広告アカウントID（数字。`act_` は付けても付けなくてもよい）。複数のアカウントを取る時はカンマ区切り（例 `111,222`）。トークン側でも、そのアカウントを見る権限が要る |
| `META_AD_ACCOUNT_ID_2` | 2つ目の広告アカウントID（任意）。入っていれば両方のアカウントを取る |

### 自動で入るもの・入らないもの

- 入る：キャンペーン、広告の名前・画像・種類、広告費・表示・クリック・LP到達・リストイン、広告のリンク先から割り出したLP。
- リストインは、Metaが数えた登録（`complete_registration` か `lead`）のうち数字がある最初の1つを使う。どれを使ったかは実行ログと `data.json` の `listinSource` に出る。固定したい時は Variables に `META_LISTIN_ACTION` を入れる。
- 入らない：`lps` の名前や段階（入口・登録後のVSLなど）、目標の数字（`targetCpa`・`monthlyGoal`）。今は入れていない（`null`）。入れると、好調／停止候補の判定と目標の線が画面に出る。手で入れた値は自動更新では消えない。
- 知らないLPへ流している広告があれば、LPは「未分類」に仮の名前で足される。

## 手で直す時（Grok Bot・人）

1. `data.json` を開く。
2. 各広告（`creatives[]`）の `daily` に、その日の1行 `{date, spend, imp, click, lpview, listin}` を足す。同じ日付の行があれば上書きする。数字が無い項目は `0`。
3. 新しい広告・LP・キャンペーンが出ていたら `creatives`・`lps`・`campaigns` に足す。
4. `updatedAt` を今の日本時間にする（例 `2026-11-24T09:00:00+09:00`）。
5. 本物の数字を入れ始めたら、先頭の `"sample": true` を消す（画面の「サンプルデータ」の表示が消える）。
6. `data.json` だけをコミットする。`index.html` は書き換えない。

クリック率・登録率・1リストインの費用・好調／停止候補は画面側で計算するので入れない。

## 今の状態（2026-11-24）

- 2026-11-24：Metaにつながり、`data.json` は本物の数字。8:30から3時間おきに自動で更新される。
- 見る場所は上の「画面」のURL。`data.json` を書き換えてコミットすると、数分で画面に出る。
- 未決事項は `データの形_GrokBot向け.md` の「まだ決まっていないこと」を参照。
