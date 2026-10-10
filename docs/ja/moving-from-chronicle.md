# Chronicle からの移行

[← Interlatch](../../README.ja.md) · [ドキュメント一覧](README.md)

Interlatch は以前 Chronicle という名前でした。名前が変わっただけの同じプログラムで、セッション、ナレッジ、設定、
ハブはそのまま使えます。移行はインストール 1 回で済みます。

## アップデートする

**コマンドラインの場合：** PyPI のパッケージ名は `interlatch` になりました（以前は `agents-chronicle`）。使っていた
エクストラ（`uv tool list --show-extras` で確認できます）を付けて切り替えます。2 つのパッケージのコマンドがぶつかるので、
先にアンインストールします。

```bash
uv tool uninstall agents-chronicle
uv tool install --python 3.13 'interlatch[app]'   # デスクトップアプリが不要なら interlatch だけ
```

**設定 › Status › Updates** の **Update** でも同じ切り替えができます。切り替えるまでは `uv tool upgrade agents-chronicle`
もそのまま使えます。最後の `agents-chronicle` のリリースが Interlatch をインストールし、両方のコマンドを残します。

**デスクトップアプリの場合：** [最新リリース](https://github.com/Chatixia-AI/agents-chronicle/releases/latest)から
`Interlatch-<version>-arm64.dmg` をダウンロードし、**Interlatch** を **アプリケーション** にドラッグして開きます。
macOS からは別のアプリに見えるため、Chronicle.app はそのまま残ります。Interlatch が起動したら削除してください。

## 自動で移行されるもの

Chronicle が入っていたコンピューターで Interlatch を初めて動かすと、設定がまとめて移行されます。
`interlatch migrate` は同じことを手動で行い、何を変えたかを表示します。移行済みのコンピューターでは何もしません。

| 対象 | 以前 | 以後 |
| --- | --- | --- |
| データフォルダー | `~/.claude-chronicle` | `~/.interlatch`。古いパスにはリンクを残すので、まだそこを指しているものも動きます |
| MCP サーバー（登録していたすべてのエージェントと MCP クライアント） | `chronicle`、ツールは `mcp__chronicle__…` | `interlatch`、ツールは `mcp__interlatch__…` |
| Claude Code のフックとステータスライン | `chronicle` を実行 | `interlatch` を実行 |
| ログイン項目（macOS の launchd） | `com.claude-chronicle.sync`、`com.claude-chronicle.ui` | `com.interlatch.sync`、`com.interlatch.ui` |
| ログイン項目（Linux の systemd） | `chronicle-sync.timer`、`chronicle-ui.service` | `interlatch-sync.timer`、`interlatch-ui.service` |
| エージェントに与えていたツールの許可 | `mcp__chronicle__…` | `mcp__interlatch__…`。エージェントがもう一度確認を求めることはありません |
| `CLAUDE.md` と `AGENTS.md` に追加した行 | `<!-- chronicle:friction:… -->` | `<!-- interlatch:friction:… -->` |

編集するファイルは、エージェントを接続するときと同じく、事前に `~/.interlatch/backups/` にバックアップします。
データベースの名前（`chronicle.db`）とフォルダー内のほかのファイルの名前は変わりません。

## そのまま使えるもの

- **`chronicle` コマンド。** `interlatch` と同じプログラムなので、`chronicle …` を呼ぶスクリプトや手癖もそのまま
  動きます。ドキュメントでは `interlatch` を使います。
- **環境変数。** `CHRONICLE_*` の変数は引き続き読み込みます。`INTERLATCH_*` の名前（`INTERLATCH_HOME`、
  `INTERLATCH_HUB_URL` など）と両方ある場合は `INTERLATCH_*` が優先されます。
- **ハブ。** ハブと、そこへ送るコンピューターは、どの順番で移行してもかまいません。古いバージョンと新しいバージョンは
  そのままやり取りでき、招待、サインイン、トークンも有効なままです。[Docker のハブ](docker.md#更新する)は、イメージ
  `ghcr.io/chatixia-ai/interlatch-hub` を使う最新の `compose.yaml` で移行します。`.env`、ボリューム、データはそのままです。
  古い `compose.yaml` のままのハブにも、古いイメージ名で各リリースが届きます。
- **Postgres へのコピー**とハブのチームストアは、スキーマもテーブルも変わりません。
- **リンク。** chronicle.chatixia.net は [interlatch.com](https://interlatch.com) に転送されます。

## VS Code 拡張機能

拡張機能は名前と ID が **Interlatch**（`chatixia.interlatch`）に変わりました。VS Code からは別の拡張機能に見えるので、
古いものが自動で置き換わることはありません。新しいものをインストールし（[VS Code 拡張機能](vscode.md)）、
**Chronicle** はアンインストールしてください。両方が入っている間は、Interlatch が一度だけそう勧めます。
`chronicle.*` の設定は引き続き読み込まれ、設定していない `interlatch.*` の項目には古い値が使われます。

うまくいかないときは[トラブルシューティング](troubleshooting.md)を参照してください。
