# 開発

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

## テストとローカルへのインストール

```bash
uv sync && uv run pytest -q        # ~300 tests, ~40 s: a fake `claude` binary and synthetic Codex, Copilot, Bob and Antigravity stores
# redeploy: --reinstall picks up uncommitted edits too (uv rebuilds on its own only when pyproject.toml, the commit or a tag changes)
uv tool install --force --reinstall --python 3.13 . && chronicle install   # install restarts the agents
```

## macOS アプリ

`uv run --extra app chronicle app` でチェックアウトから起動できます（Open at Login など、バンドルでしか意味のない
メニュー項目は非表示）。`./packaging/macos/build.sh` は `dist/Chronicle.app` と
`dist/Chronicle-<version>-<arch>.dmg` をビルドします（PyInstaller、約 30 秒。`packaging/macos/Chronicle.spec`）。1 つのバイナリが、
引数なしではアプリとして、引数ありでは CLI として動き、フックと MCP サーバーはこれを CLI として実行します。署名なしのビルドはアドホック
署名となり、ビルドした Mac でのみ動きます。配布するには `CHRONICLE_CODESIGN_IDENTITY`（Developer ID
Application 証明書）と `NOTARY_KEYCHAIN_PROFILE`（`xcrun notarytool store-credentials` で作成）を設定すると、スクリプトが
DMG の署名・公証・ステープルまで行います。`uv run --group build python packaging/macos/make_icon.py` で、
コミット済みの `packaging/macos/icon-blueprint.webp` から macOS の `.icns`、README のアイコン、ダッシュボードのロゴ、
favicon、スマートフォンのホーム画面用アイコンを再生成できます。PNG はどの OS でも生成でき、`.icns` には macOS の
`iconutil` が必要です。`desktop.py` は
pywebview の Cocoa アプリデリゲートを拡張しているため、pywebview を `<7` に固定しています。

## 継続的インテグレーション

`.github/workflows/ci.yml` は、すべてのプルリクエストと `main` へのプッシュで動きます。テストスイート（`test`。`main` の
必須チェック）、pre-commit のフック（`lint`）、ロックした依存関係への `pip-audit`（`audit`）です。Dependabot が `uv.lock` とワークフローのアクションの更新を
毎週提案します。アクションはコミットハッシュで固定しています（バージョンは横のコメントにあります）。リポジトリの設定で、
GitHub のシークレットスキャン、プッシュ保護、CodeQL のコードスキャンを有効にしています。

### pre-commit のフック

一度 `uvx pre-commit install` を実行すると、`.pre-commit-config.yaml` がコミットごとに確認します。マージの印、YAML と TOML、
600 KB を超えるファイル、秘密鍵などのシークレット（gitleaks）、行末の空白と最後の改行、`ruff check`、`uv.lock` と
`pyproject.toml` の一致、ワークフロー（zizmor）、ダッシュボードの JavaScript が読めること（`node --check`）です。Ruff は
バグになりそうな箇所だけを見ます（pyflakes と bugbear）。コードは独自のレイアウトを保つので、整形はしません。
`uvx pre-commit run --all-files` ですべてを手動で実行できます。偽のキーが必要なテストは、その行に `# gitleaks:allow` を付けます。

## リリース

バージョンはどこにも書きません。git のタグから決まります（hatch-vcs）。タグの付いたコミットはそのバージョン
（`v0.7.0` → `0.7.0`）、その後のコミットは次のパッチの開発版（`0.7.1.dev3+g1a2b3c4`）としてビルドされ、ソースの
チェックアウトでは Status ページにこれが表示されます。

リリースするには、変更点を作業のたびに `CHANGELOG.md` の `## Unreleased` に書いておき、`main` で **Actions → Release →
Run workflow** を実行して `patch`、`minor`、`major` のどれかを選びます。`.github/workflows/release.yml` が最新のタグから
次のバージョンを決め、テストを実行し、タグと GitHub リリースを作成し（Unreleased の節がリリースノートになります）、
`agents-chronicle` を PyPI に公開し（Trusted Publishing、環境 `pypi`）、DMG をリリースに添付します（`MACOS_*` /
`APPLE_*` シークレットが設定されていれば署名・公証済み。詳細はワークフローの先頭を参照）。最後に、`## Unreleased` を
`## <version> (<date>)` に変えるプルリクエストを開きます。次のリリースの前にマージしてください。マージするまでは
リリース済みの内容が Unreleased に残っているため、次の実行は最初のステップでその旨を伝えて止まります。このリポジトリで
GitHub Actions がプルリクエストを作れない設定の場合は、実行の Summary に開くためのリンクが出ます。
既定の `dry run` はテストを実行して DMG をワークフローの成果物として保存するだけで、何も公開しません。
GitHub で `v<version>` タグのリリースを手動で公開する方法も引き続き使えます。

### 最初のリリースの前に一度だけ必要な設定

1. PyPI で *pending publisher* を追加します（Account → Publishing）：プロジェクト `agents-chronicle`、オーナー
   `Chatixia-AI`、リポジトリ `agents-chronicle`、ワークフロー `release.yml`、環境 `pypi`。
2. GitHub リポジトリで `pypi` という名前の環境を作成します（Settings → Environments）。
3. 署名・公証済みの DMG を配布するには（Apple Developer Program への加入が必要）：*Developer ID Application*
   証明書を鍵ごと `.p12` として書き出し、シークレット `MACOS_CERT_P12`（ファイルの base64）、
   `MACOS_CERT_PASSWORD`、`MACOS_CODESIGN_IDENTITY`、`APPLE_ID`、`APPLE_TEAM_ID`、`APPLE_APP_PASSWORD`
   （account.apple.com で発行するアプリ用パスワード）を追加します。これらがない場合、DMG はアドホック署名となり、
   利用者は「プライバシーとセキュリティ」で許可する必要があります。
4. 任意：Settings → Actions → General → **Allow GitHub Actions to create and approve pull requests** をオンにすると、
   リリースが変更履歴のプルリクエストをリンクではなく自分で開きます。

## ドキュメントサイト

<https://chronicle.chatixia.net/docs/> は `docs/` と README から MkDocs Material でそのまま生成されます。`README.md` と
`README.ja.md` がホームページになり、`docs/` の外を指すリンクは `docs/_site/hooks.py` が GitHub へのリンクに書き換えます。
ランディングページを含むサイト全体は [Chatixia-AI/chronicle-site](https://github.com/Chatixia-AI/chronicle-site) にあり、
このドキュメントをそのままビルドしてすべてを公開します。`.github/workflows/docs.yml` はプルリクエストごとにビルドを確認し、
`main` でドキュメントが変わると chronicle-site に再ビルドを依頼します（毎日の再ビルドもあります）。

```bash
uv run --only-group docs mkdocs serve            # http://127.0.0.1:8000/ でプレビュー（保存で再読み込み）
uv run --only-group docs mkdocs build --strict     # CI と同じ：リンクやアンカーが壊れていると失敗
```

## 図

`docs/diagrams/` の図は `.excalidraw.svg` ファイルです。画像として表示され、Excalidraw の VS Code 拡張機能
（`pomdtr.excalidraw-editor`）または excalidraw.com で編集できます。保存すると同じファイルに書き戻されます。

## コードの構成

`parser.py`（Claude のトランスクリプト形式）、`codex_parser.py`（Codex のロールアウト）、`copilot_parser.py`（Copilot の
エージェントセッション＋VS Code のチャットログ）、`bob_parser.py`（Bob のタスク）、`antigravity_parser.py`（Antigravity のステップログ）、`agents.py`（エージェント名）、`connectors.py`（ソース）、
`ingest.py`（アーカイブ＋保存）、`digest.py` / `analyze.py` /
`llm.py`（分析）、`synthesize.py`（ナレッジベース）、`diagram.py`（アーキテクチャ図）、`artifacts.py`（セッションが作ったものと、その今の状態）、`glossary.py`、`reviews.py`、`worker.py`（キュー）、`server.py` ＋ `web/`
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
