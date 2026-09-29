# データとプライバシー

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

**マシンの外に送られるもの：** 1 つだけです。セッションを分析するとき、そのセッションをまとめた要約（機密情報は先に伏せ字にします）が、
あなた自身の Claude Code のログインを通じて `claude -p` で Claude に送られます。トランスクリプトを生成したのと同じサービスです。
Chronicle の作者やその他のサービスには何も送られず、テレメトリもありません。

| ローカルに保存されるもの | 場所 |
| --- | --- |
| データベース：セッション、イベント、ナレッジ、用語集、振り返り | `~/.claude-chronicle/chronicle.db`（SQLite） |
| 元のトランスクリプト（無期限に保存、gzip） | `~/.claude-chronicle/archive/` |
| Markdown 保管庫 | `~/.claude-chronicle/notes/` |
| ログ | `~/.claude-chronicle/logs/` |
| Chronicle が編集したエージェントの設定ファイルのバックアップ | `~/.claude-chronicle/backups/` |
| アプリの起動スクリプトとウインドウの保存領域 | `~/.claude-chronicle/bin/chronicle`、`~/.claude-chronicle/webview/` |

## 詳細

- **伏せ字処理。** API キー、トークンなどの機密情報は、呼び出しの前に要約の中で置き換えられます。生のアーカイブには
  元のトランスクリプトがそのまま残りますが、それはあなたのディスク上だけです。
- **分析はサンドボックスで実行されます。** `claude -p` は `--no-session-persistence --safe-mode --tools ""
  --strict-mcp-config` 付きで実行されます：分析そのもののトランスクリプトは書き出されず、フック、プラグイン、MCP サーバーは読み込まれず、
  モデルは回答することしかできません。`analysis.auto = false` で自動分析をオフにできます。
- **ダッシュボード**は 127.0.0.1 にのみバインドし、外部の `Host` ヘッダーを拒否し（DNS リバインディング対策）、状態を変更するリクエストには
  独自ヘッダーを必須にしています（CSRF 対策）。アプリのウインドウでは、ページが呼び出せるウインドウ操作は 3 つ（テーマ、ドラッグ、
  ズーム）だけです。
- **他のエージェントのデータは読み取るだけです。** SQLite データベースは読み取り専用で開き、スナップショットとしてアーカイブします。Bob の
  ログイン状態は一切読みません。エージェントを接続するとその MCP 設定を編集しますが、事前に `~/.claude-chronicle/backups/` に
  バックアップします。
- **削除。** `chronicle forget <id> [--delete-transcript]` でセッションを完全に削除できます。`chronicle uninstall
  --purge` はすべてを削除します。
