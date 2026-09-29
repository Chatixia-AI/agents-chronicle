# コマンドライン

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

| コマンド | |
| --- | --- |
| `chronicle install [--yes] [--dry-run]` | セットアップ：見つかったエージェントを一覧にし、記録するものを尋ね、取り込み、ダッシュボードを起動（[インストール](install.md#コマンドライン)） |
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
| `chronicle import <zip> [--analyze]` | claude.ai または ChatGPT のデータエクスポート（.zip、展開したフォルダー、`conversations.json`）からチャットを取り込み（繰り返し可）。[ソース](sources.md)を参照 |
| `chronicle forget <id> [--delete-transcript]` | セッションを保管庫から完全に削除（再取り込みされません） |
| `chronicle sources` | 接続中のエージェントと、その記録方法 |
| `chronicle connect <agent>` / `disconnect <agent>` | `claude`、`codex`、`codex-cloud`、`copilot`、`bob` の記録を開始／停止（データは残ります） |
| `chronicle connect <client>` / `disconnect <client>` | `claude-desktop`、`cursor`、`windsurf`、`gemini` に MCP サーバーを追加／削除 |
| `chronicle mcp [--print-config]` | MCP サーバーを実行（クライアントが起動します）、またはほかの MCP クライアント用の設定項目を出力 |
| `chronicle status` | 状態確認：フック、エージェント、MCP、キュー、失敗 |
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
