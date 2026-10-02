# コマンドライン

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

| コマンド | |
| --- | --- |
| `chronicle install [--yes] [--analyze all\|N\|later] [--[no-]notify-updates] [--dry-run]` | セットアップ：見つかったエージェントを一覧にし、記録するものを尋ね、取り込み、今すぐ進捗付きで分析するか尋ね（用語集とマップはここから作られます）、ダッシュボードを起動（[インストール](install.md#コマンドライン)） |
| `chronicle app` | デスクトップアプリ（ウインドウ＋メニューバー）。`app` エクストラが必要 |
| `chronicle ui [--open]` | ダッシュボード（インストール後は :8765 で常時稼働。稼働中なら `chronicle ui` がそう表示し、`--open` でそれを開きます）。Sessions、Knowledge、Projects、Glossary は Cards と List（並べ替え可能な表。行をクリックで詳細）を切り替えられ、ページごとに記憶されます |
| `chronicle sessions [-p project] [--since 7d]` | セッションの一覧 |
| `chronicle show <id-prefix> [--transcript\|--markdown\|--json]` | セッションの概要、または会話全体 |
| `chronicle search <words>` | トランスクリプトとナレッジの全文検索（言語を問わず、3 文字以上） |
| `chronicle knowledge [query] [-k gotcha] [-p project]` | 抽出されたナレッジの閲覧 |
| `chronicle projects` / `chronicle stats [--since 30d]` | プロジェクト別と全体の統計 |
| `chronicle analyze <id> \| --pending [--limit N] [--dry-run] [--backend codex]` | 今すぐ分析（`--dry-run` は要約のサイズを表示するだけで、トークンを使いません。`--backend` はこの実行だけで使うエージェントを選びます） |
| `chronicle synthesize [--project P] [--global] [--all]` | ナレッジベースを再構築 |
| `chronicle export [--full]` | Markdown 保管庫を書き直す |
| `chronicle export <id>… [--format md\|json\|raw] [--out PATH]` | セッションを書き出す：1 件なら 1 ファイル、複数なら .zip（`raw` は元のトランスクリプト） |
| `chronicle glossary [term] [-p project] [--rebuild --all] [--themes]` | あなたの語彙：社内名称、略語、業務用語と、その定義と使われ方。`--themes` で大きいカテゴリをマップ用のテーマに分けます |
| `chronicle review [2026-W39\|current]` | 分析モデルが書く週次の振り返り（週が終わるたびに自動作成） |
| `chronicle import <zip> [--analyze] [--screen]` | claude.ai または ChatGPT のデータエクスポート（.zip、展開したフォルダー、`conversations.json`）からチャットを取り込み（繰り返し可）。`--screen` で取り込み後すぐに選別します。[ソース](sources.md)を参照 |
| `chronicle screen [--source chatgpt\|claude-ai] [--sample N] [--dry-run] [--redo]` | 取り込んだチャットを、各チャットの冒頭だけを読んで「分析する価値あり」「たぶん」「価値なし」に分けます（[取り込んだチャットの選別](sources.md#取り込んだチャットの選別)） |
| `chronicle screen --list analyze\|maybe\|skip [--json]` / `--queue [--maybe]` | 選別結果ごとにチャットと理由を表示。分析する価値ありのチャット（`--maybe` で「たぶん」も）を背景の分析待ちに入れます |
| `chronicle friction [-p project] [--days N] [--json] [--noise]` | うまくいかないこと：セッションで繰り返す失敗の原因（セッション数、プロジェクト数、最後に見た日、まだ起きているか、推移）と、失敗の多いツール。`--noise` で想定内の失敗も表示（[提案](suggestions.md#うまくいかないこと)） |
| `chronicle suggest [-p project] [--all] [--json]` | 確認待ちの修正案：指示ファイルの行、設定の変更、セットアップ手順。適用するまで何も書き込みません（[提案](suggestions.md)） |
| `chronicle suggest show\|apply\|dismiss\|done\|undo ID… [--yes] [--reason R]` | 差分を表示、適用（`--yes` がなければ確認し、ファイルをバックアップ）、二度と提案しない、実行したセットアップ手順を完了にする、適用したものを取り消す |
| `chronicle suggest move ID --to user\|project` | 確認待ちの行をユーザーレベルのファイルに、または元のプロジェクトのファイルに移す。教訓や原因ごとに記憶します（[行を移す](suggestions.md#行を移す)） |
| `chronicle suggest refresh` | 最新のセッションとナレッジから今すぐ提案を探す（バックグラウンド同期も実行のたびに行います） |
| `chronicle forget <id> [--delete-transcript]` | セッションを保管庫から完全に削除（再取り込みされません） |
| `chronicle sources` | 接続中のエージェントと、その記録方法 |
| `chronicle connect <agent>` / `disconnect <agent>` | `claude`、`codex`、`codex-cloud`、`copilot`、`bob`、`antigravity` の記録を開始／停止（データは残ります） |
| `chronicle connect <client>` / `disconnect <client>` | `claude-desktop`、`cursor`、`windsurf`、`gemini` に MCP サーバーを追加／削除 |
| `chronicle mcp [--print-config]` | MCP サーバーを実行（クライアントが起動します）、またはほかの MCP クライアント用の設定項目を出力 |
| `chronicle status` | 状態確認：フック、エージェント、MCP、キュー、失敗 |
| `chronicle tailnet on\|off\|status [--anyone]` | Tailscale Serve でダッシュボードをスマートフォンやほかのデバイスから開けるようにする。通すのはあなたの Tailscale ログインだけ（`--anyone` で tailnet の全員）（[スマートフォンとほかのコンピューター](devices.md#スマートフォン)） |
| `chronicle hub enable [--rotate]` | このコンピューターをほかのコンピューターのハブにする。ほかのコンピューターで実行する `chronicle hub join` のコマンドを表示 |
| `chronicle hub join <address> --token <token>` / `hub leave` | このコンピューターのセッションをここで記録せずにハブへ送る、またはやめる（[ほかのコンピューター](devices.md#ほかのコンピューター)） |
| `chronicle hub status` / `hub disable` | このハブに送ってくるコンピューターの一覧／受け付けをやめる |
| `chronicle push` | ハブに参加したコンピューターで：新しいセッションを今すぐ送る（フックとバックグラウンド同期も送ります） |
| `chronicle config [edit]` | `~/.claude-chronicle/config.toml` を表示または編集 |
| `chronicle config set <section.key> <value>` | 設定を 1 つ変更。例：`chronicle config set analysis.backend codex`（[設定](configuration.md)） |

## その他の使い方

**Markdown 保管庫：** `~/.claude-chronicle/notes`（Obsidian の保管庫として開けます）：`Home.md`、YAML フロントマター付きの
`Sessions/YYYY/MM/*.md`、`Projects/*.md`（ナレッジベース＋セッション一覧）、`Knowledge/<Kind>.md`、`Reviews/YYYY-Www.md`、
`Glossary.md`、`Global Playbook.md`。

**エージェントの中から**（MCP ツール。Claude Code と接続済みの各エージェントに登録）：`search_knowledge`、`search_sessions`、
`get_session`、`get_transcript`、`project_knowledge`、`glossary`、`recent_sessions`。たとえば *「このエラー、前にも出た？」* や
*「deployer_ip のルールって何だっけ？」* のように尋ねられます。

MCP サーバーは、エージェントを接続したときに登録されます（[ソース](sources.md)を参照）。各ツールの説明と、ほかのクライアントの
接続方法は [MCP サーバー](mcp.md)にあります。
