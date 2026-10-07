# データとプライバシー

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

**マシンの外に送られるもの：** 1 つだけです。セッションを分析するとき、そのセッションをまとめた要約（機密情報は先に伏せ字にします）が、
分析用に選んだものに送られます：あなた自身のログインで Claude Code（`claude -p`、既定）なら Anthropic に、Codex（`codex exec`）
なら OpenAI に、Bob Shell（`bob run`）ならあなたの Bob API キーで IBM に、または設定した[モデルプロバイダー](analysis.md#モデルプロバイダー)にあなた自身のキーで送られます（あなたの
コンピューターの Ollama なら、何も外に出ません）。
Chronicle の作者やその他のサービスには何も送られず、テレメトリもありません。ほかの接続の 1 つは
アップデート確認です。pypi.org に最新のバージョン番号を問い合わせるだけで、あなたに関する情報は送りません。Status ページで **Check for updates** を押したときに実行され、同じ場所の **Check for updates daily** か **Notify me about new versions** をオンにした場合だけ 1 日 1 回実行されます（どちらも既定はオフ。後者は `chronicle install` が尋ねます）。Codex Cloud を接続した場合は、
同期のたびに `codex cloud` CLI も実行され、Codex のログインで OpenAI からあなた自身のタスクを取得します。こちらから何かを送ることはありません。
claude.ai や ChatGPT のエクスポートを取り込むときはチャットだけを読み、アカウントのファイル（`users.json`、`user.json`）は開きません。
提案した行が公開リポジトリに入る前に警告するため、GitHub のリモートがあるプロジェクトでは、あなた自身の `gh` のログインで
`gh repo view` を実行します。GitHub に送るのはリポジトリの名前だけで、結果は 1 週間覚えておきます。`gh` が
なければ何も送りません（[提案](suggestions.md#プライバシー)）。

**スマートフォンやほかのコンピューターと使う場合**（[スマートフォンとほかのコンピューター](devices.md)）も、あなた自身のデバイスの外には
何も出ません。`chronicle tailnet on` はダッシュボードを Tailscale のネットワーク内で、あなたの Tailscale ログインだけに開きます。
ハブに参加したコンピューターは、自分の元のセッションファイルを（アーカイブと同じく伏せ字なしで）tailnet 内の HTTPS でハブに送ります。

| ローカルに保存されるもの | 場所 |
| --- | --- |
| データベース：セッション、イベント、ナレッジ、用語集、振り返り | `~/.claude-chronicle/chronicle.db`（SQLite） |
| 元のトランスクリプト（無期限に保存、gzip） | `~/.claude-chronicle/archive/` |
| Markdown 保管庫 | `~/.claude-chronicle/notes/` |
| ログ | `~/.claude-chronicle/logs/` |
| Chronicle が編集したエージェントの設定ファイルと指示ファイルのバックアップ | `~/.claude-chronicle/backups/` |
| セッションごとのステータスラインの使用量（`--statusline` を使った場合のみ） | `~/.claude-chronicle/statusline/` |
| アプリの起動スクリプトとウインドウの保存領域 | `~/.claude-chronicle/bin/chronicle`、`~/.claude-chronicle/webview/` |
| このコンピューターの ID と名前、ハブのトークン（あなただけが読めます） | `~/.claude-chronicle/machine.json`、`~/.claude-chronicle/hub-token` |
| ハブで：ほかのコンピューターが送ってきたセッションファイル | `~/.claude-chronicle/machines/` |

## 詳細

- **システムマップはマニフェストを読みます。** 各プロジェクトが何でできているかを描くため、プロジェクトフォルダーにある
  決まった短いリストのファイルだけを、2 階層下まで読み取り専用で読みます：パッケージのマニフェスト、compose ファイル、
  Dockerfile、Terraform、GitHub ワークフロー、vite の設定、`.env.example`、デプロイ設定。`.env` やソースコードは読まず、
  何も保存も送信もしません（マップはメモリ上で作り直します）。git のリモートは認証情報を除いて表示します。
  `[systems] read_manifests = false` で無効にできます（[システムマップ](dashboard.md#システムマップ)）。
- **伏せ字処理。** API キー、トークンなどの機密情報は、呼び出しの前に要約の中で置き換えられます。生のアーカイブには
  元のトランスクリプトがそのまま残りますが、それはあなたのディスク上だけです。
- **分析はサンドボックスで実行されます。** 分析そのもののセッションは書き出されず、あなたのフック、プラグイン、MCP サーバー、
  指示ファイルは読み込まれず、モデルは回答することしかできません。`claude -p` は `--no-session-persistence --safe-mode --tools ""
  --strict-mcp-config` 付きで実行されます。`codex exec` は `--ephemeral` と `--ignore-user-config` 付きで、すべてのツール機能を
  切った読み取り専用のサンドボックスで実行され、ツール呼び出しのあとに来た応答は Chronicle が捨てます
  （[詳細](analysis.md#分析の仕組み)）。モデルプロバイダーには、ツールを含まない素の API リクエストを送ります。
  `analysis.auto = false` で自動分析をオフにできます。
- **プロバイダーの API キー**は Chronicle のフォルダーの `provider-keys.json`（モード 600）に保存され、`config.toml` には
  入りません。ダッシュボードがキーをブラウザーに送り返すことはありません。
- **ダッシュボード**は 127.0.0.1 にのみバインドし、外部の `Host` ヘッダーを拒否し（DNS リバインディング対策）、状態を変更するリクエストには
  独自ヘッダーを必須にしています（CSRF 対策）。アプリのウインドウでは、ページが呼び出せるウインドウ操作は 3 つ（テーマ、ドラッグ、
  ズーム）だけです。Tailscale Serve 経由では `[server] allowed_hosts` の名前にだけ応答し、`[server] allowed_users` の
  Tailscale ログインだけを通します（このヘッダーは同じコンピューターの Serve から来たものだけを信用します）。ハブがほかの
  コンピューターのファイルを受け取るのは、そのトークンがあるときだけです（`chronicle hub enable --rotate` で作り直せます）。
- **書き出し**（セッションページの Export、または Sessions の一覧で選んだセッションの Export）は、Markdown と JSON では
  ダッシュボードの表示と同じく機密情報を伏せ字にします。**Original transcript** はエージェント自身のファイルをそのまま渡すため
  伏せ字になりません。共有する前に確認してください。
- **MCP ツール**はデータベースを読んで stdio で答えるだけで、ネットワークで待ち受けるものはありません。その結果はクライアントの会話に
  加わるため、そのクライアントのモデルに届きます（要約と同じく機密情報は伏せ字にします）。セッションを見せてもよいモデル提供元の
  クライアントにだけサーバーを追加してください。[MCP サーバー](mcp.md#プライバシー)を参照してください。
- **他のエージェントのデータは読み取るだけです。** SQLite データベースは読み取り専用で開き、スナップショットとしてアーカイブします。Bob の
  ログイン状態は一切読みません。Antigravity からアーカイブするのは会話ログと Markdown の成果物だけです。エージェントを接続するとその MCP 設定を編集しますが、事前に `~/.claude-chronicle/backups/` に
  バックアップします。
- **指示ファイルと `~/.claude.json` に書き込むのは、提案を適用したときだけです。** Chronicle は `CLAUDE.md` や `AGENTS.md` の
  自分の `<!-- BEGIN chronicle -->` ブロックの中だけに 1 行を加えるか、`~/.claude.json` に足りない Playwright MCP の引数を
  加えます。どのファイルも事前に `~/.claude-chronicle/backups/` にバックアップし、**Undo** で変更を取り消せます。セットアップ
  手順は表示するだけで、Chronicle が実行したり、シェルの起動ファイルを編集したりすることはありません。
  [提案](suggestions.md)を参照してください。
- **削除。** `chronicle forget <id> [--delete-transcript]` でセッションを完全に削除できます。`chronicle uninstall
  --purge` はすべてを削除します。
