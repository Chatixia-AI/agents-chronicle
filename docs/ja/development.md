# 開発

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

## テストとローカルへのインストール

```bash
uv sync && uv run pytest -q        # 88 tests, ~12 s: a fake `claude` binary and synthetic Codex, Copilot and Bob stores
# redeploy: --reinstall is required, uv caches local builds keyed on pyproject.toml only
uv tool install --force --reinstall --python 3.13 . && chronicle install   # install restarts the agents
```

## macOS アプリ

`uv run --extra app chronicle app` でチェックアウトから起動できます（Open at Login など、バンドルでしか意味のない
メニュー項目は非表示）。`./packaging/macos/build.sh` は `dist/Chronicle.app` と
`dist/Chronicle-<version>-<arch>.dmg` をビルドします（PyInstaller、約 30 秒。`packaging/macos/Chronicle.spec`）。1 つのバイナリが、
引数なしではアプリとして、引数ありでは CLI として動き、フックと MCP サーバーはこれを CLI として実行します。署名なしのビルドはアドホック
署名となり、ビルドした Mac でのみ動きます。配布するには `CHRONICLE_CODESIGN_IDENTITY`（Developer ID
Application 証明書）と `NOTARY_KEYCHAIN_PROFILE`（`xcrun notarytool store-credentials` で作成）を設定すると、スクリプトが
DMG の署名・公証・ステープルまで行います。`packaging/macos/make_icon.py` でアイコン（`.icns` と、ダッシュボードとソースから起動したアプリのウインドウが使う `web/icon.png`）を再描画できます。`desktop.py` は
pywebview の Cocoa アプリデリゲートを拡張しているため、pywebview を `<7` に固定しています。

## リリース

`pyproject.toml` の `version` を上げ、`v<version>` タグで GitHub リリースを公開します。
`.github/workflows/release.yml` がテストを実行し、`agents-chronicle` を PyPI に公開し（Trusted Publishing、
環境 `pypi`）、DMG をリリースに添付します（`MACOS_*` / `APPLE_*` シークレットが設定されていれば署名・公証済み。
詳細はワークフローの先頭を参照）。ワークフローを手動で実行すると（**Actions → Release → Run workflow**）
ドライランになり、テストを実行して DMG をワークフローの成果物として保存するだけで、何も公開しません。

### 最初のリリースの前に一度だけ必要な設定

1. PyPI で *pending publisher* を追加します（Account → Publishing）：プロジェクト `agents-chronicle`、オーナー
   `kayeungadrian-tam`、リポジトリ `agents-chronicle`、ワークフロー `release.yml`、環境 `pypi`。
2. GitHub リポジトリで `pypi` という名前の環境を作成します（Settings → Environments）。
3. 署名・公証済みの DMG を配布するには（Apple Developer Program への加入が必要）：*Developer ID Application*
   証明書を鍵ごと `.p12` として書き出し、シークレット `MACOS_CERT_P12`（ファイルの base64）、
   `MACOS_CERT_PASSWORD`、`MACOS_CODESIGN_IDENTITY`、`APPLE_ID`、`APPLE_TEAM_ID`、`APPLE_APP_PASSWORD`
   （account.apple.com で発行するアプリ用パスワード）を追加します。これらがない場合、DMG はアドホック署名となり、
   利用者は「プライバシーとセキュリティ」で許可する必要があります。

## 図

`docs/diagrams/` の図は `.excalidraw.svg` ファイルです。画像として表示され、Excalidraw の VS Code 拡張機能
（`pomdtr.excalidraw-editor`）または excalidraw.com で編集できます。保存すると同じファイルに書き戻されます。

## コードの構成

`parser.py`（Claude のトランスクリプト形式）、`codex_parser.py`（Codex のロールアウト）、`copilot_parser.py`（Copilot の
エージェントセッション＋VS Code のチャットログ）、`bob_parser.py`（Bob のタスク）、`agents.py`（エージェント名）、`connectors.py`（ソース）、
`ingest.py`（アーカイブ＋保存）、`digest.py` / `analyze.py` /
`llm.py`（分析）、`synthesize.py`（ナレッジベース）、`glossary.py`、`reviews.py`、`worker.py`（キュー）、`server.py` ＋ `web/`
（ダッシュボード）、`mcp_server.py`、`export_md.py`、`hooks.py` / `install.py`、`desktop.py`（macOS アプリ）、`cli.py`。`packaging/macos/` がアプリをビルドします。

## デモデータ

`docs/demo/make_demo.py` は、架空のセッションから Chronicle のホームを作ります：5 つのプロジェクトと約 6 週間分の作業を持つ
架空の開発者です。合成した Claude Code のトランスクリプトを書き出し、それに対して実際の処理（同期、分析、ナレッジベース、用語集、
週次の振り返り）を実行します。代役の `claude` が、手書きの要約とナレッジで各分析に答えるため、費用はかからず、ログインも不要です。
`docs/images/` のスクリーンショットはこのデータから作られています。

```bash
uv run python docs/demo/make_demo.py /tmp/chronicle-demo
CHRONICLE_HOME=/tmp/chronicle-demo/home uv run python -m chronicle ui --port 8898 --open
```
