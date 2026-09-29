# トラブルシューティング

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

まずは `chronicle status`（またはダッシュボードの **Settings › Status**）を実行してください。フック、バックグラウンドエージェント、
MCP サーバー、`claude` CLI を確認し、最近の分析の失敗を一覧表示します。ログは `~/.claude-chronicle/logs/` にあります
（すべてのログは `chronicle.log`、セッション終了フックのログは `hooks.log`）。

## インストールとアプリ

**macOS に「“Chronicle”は開けません」や「開発元を検証できません」と表示される。** そのリリースは公証されていません。
**システム設定 → プライバシーとセキュリティ** を開き、Chronicle のメッセージの横にある **このまま開く** をクリックして確認してください。

**アプリを使っているのに、Status と Sources で *Background sync* が停止中と表示される。** これらはコマンドライン版のインストールが
設定する launchd エージェントしか確認しません。アプリは自身で 15 分ごとの同期を行っており、最終同期時刻はメニューバーのメニューで確認できます。

**アプリで `analysis.backfill = false` が効かない。** アプリの Connect は、`chronicle install` が記録するインストール日を記録しないため、
接続前のセッションも分析されます。`~/.claude-chronicle/bin/chronicle install --no-launchd --no-ui` を一度実行してください。
インストール日が記録され、フックと MCP サーバーが再登録されます。

**アプリのウインドウをドラッグできない。** ツールバーの何もない部分か、信号機ボタンの横の帯をドラッグしてください。ツールバー内の
ボタンやリンクはクリックにしか反応しません。ソースから起動している場合は、最新のチェックアウトで `uv run --extra app chronicle app` を実行してください。

**メニューバーに Chronicle ではなく「python3」と表示される。** 古いチェックアウトからアプリを起動した場合にだけ起こります。
DMG 版では常に Chronicle と表示されます。

**ダッシュボードが :8765 にない。** 8765 が使用中の場合（たとえばコマンドライン版のダッシュボードエージェントが使っている場合）、
アプリは空いているポートを使います。メニューバーのメニューの **Open in Browser** で正しいポートが開きます。

**`chronicle ui` が「Address already in use」で失敗する、または再インストール後もダッシュボードが古いまま。** コマンドライン版の
launchd エージェントがすでに :8765 でダッシュボードを提供しており、起動時のコードのまま動き続けています。
`launchctl kickstart -k gui/$(id -u)/com.claude-chronicle.ui` で再起動するか、**設定 › Status › Updates** からアップデートしてください
（自動で再起動します。[アップデート](install.md#アップデート)）。別のダッシュボードを動かすには `chronicle ui --port <n>` を使います。

## 記録

**新しいセッションが表示されない。** Claude Code のセッションは `SessionEnd` フックを通じて数秒で取り込まれ、それ以外は
15 分ごとの同期で取り込まれます。`chronicle status` でフックを確認し、`chronicle sync` を実行すると今すぐ取り込めます。
Codex にはセッション終了フックがないため、Codex のセッションはしばらくアイドルになってから表示されます。

**古い Claude Code のセッションがない。** Claude Code は 30 日でトランスクリプトを削除します。Chronicle は一度見たものはすべて保存し、
それより古いセッションについては `~/.claude/history.jsonl` からプロンプト（のみ）を復元して、*history* として表示します。

**記録したくないプロジェクトがある。** 設定の `sources.exclude_projects` に glob を追加するか、`chronicle forget <id>` で
セッションを完全に削除してください。

## 分析

**何も分析されない。** 分析には、ログイン済みの `claude` CLI が必要です。`chronicle status` で `claude` がどこで見つかったかを
確認できます。アプリはログインシェルの PATH を読み込むため、npm や Homebrew でインストールした `claude` も見つかります。
セッションは、終了するか `analysis.idle_minutes` の間アイドルになると分析されます。

**「usage limit」で分析が止まった。** Claude が使用量の上限や認証のエラーを返すと、Chronicle は分析を 1 時間停止し、その後自動で
再開します。その他の失敗は間隔を空けて再試行します（30 分、2 時間、8 時間）。セッションページの **Analyze now** で、すぐに再試行できます。

**未分析分にかかる費用を先に確認したい。** `chronicle analyze --pending --dry-run` はトークンを使わずにキューの規模を確認します。
`analysis.max_budget_usd` で 1 回の呼び出しの上限を設定でき、`analysis.auto = false` で自動分析を止められます。

## 最初からやり直す

`chronicle uninstall` はフック、バックグラウンドエージェント、MCP の登録を削除し、データは残します。
`chronicle uninstall --purge` はデータも削除します。アプリを使っている場合は、**Open at Login** もオフにしてからアプリを削除してください。
