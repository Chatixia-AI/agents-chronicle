# インストール

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

Chronicle は macOS で動作し、分析を行うためにログイン済みの [Claude Code](https://claude.com/claude-code)（`claude`）が必要です。使い方は 2 通りあり、どちらも `~/.claude-chronicle` の同じデータを使うため、併用できます。

## デスクトップアプリ

1. [最新リリース](https://github.com/kayeungadrian-tam/agents-chronicle/releases/latest)から
   `Chronicle-<version>-arm64.dmg` をダウンロードします（Apple シリコン、macOS 13 以降）。
2. 開いて **Chronicle** を「アプリケーション」フォルダにドラッグし、そこから起動します。
3. 初回起動時に **Connect** を選ぶと、Claude Code のセッションの記録が始まります。`SessionEnd` フックと MCP サーバーが
   追加され（`chronicle connect claude` と同じ）、Chronicle がログイン時に起動するようになります。

macOS に「“Chronicle”は開けません」や「開発元を検証できません」と表示された場合、そのリリースは公証されていません：
**システム設定 → プライバシーとセキュリティ** を開き、Chronicle のメッセージの横にある **このまま開く** をクリックして確認してください。
Intel 版はまだありません。Intel Mac ではコマンドラインでインストールしてください。

以降、Chronicle はメニューバーに常駐します。ダッシュボードを専用ウインドウで表示し、15 分ごとのバックグラウンド同期も
アプリ自身が行うため、launchd エージェントは不要です。ウインドウを閉じても動き続けます。ウインドウにはタイトルバーがなく、
サイドバーは macOS ネイティブのガラス（ウインドウの背後をぼかします）で、その上に信号機ボタンが載ります。ウインドウはツールバーか
サイドバー上端の帯をドラッグして動かします。メニューバーアイコンの項目：

| メニュー項目 | |
| --- | --- |
| Open Chronicle / Open in Browser | ダッシュボードをアプリのウインドウ、またはブラウザで開く |
| Sync Now | 次の 15 分ごとの実行を待たずに、今すぐアーカイブ・取り込み・分析を行う。すぐ上の行に最終同期時刻を表示 |
| Connect Claude Code… | Claude Code が未接続のときに表示（初回起動時に *Not Now* を選んだ場合） |
| Open at Login | 接続後はオン。オフにすると、自分で開いたときだけ Chronicle が動きます |
| Install Command-Line Tool | アプリ内蔵の `chronicle` コマンドを `~/.local/bin` にリンク（既に存在する場合は何もしません） |
| Open Data Folder | `~/.claude-chronicle` |

Codex、Copilot、Bob はダッシュボードの **Sources** ページから接続します。フックと MCP の登録は
`~/.claude-chronicle/bin/chronicle` を指しています。これはアプリが起動のたびに書き直す小さなスクリプトなので、
アプリを移動・更新しても壊れません。アプリを終了すると、次に起動するまで同期は止まります。終了で中断された分析は、
次の同期で改めて実行されます。

Chronicle を削除するには、`~/.claude-chronicle/bin/chronicle uninstall` を実行し（フックと MCP
サーバーを削除。データは残ります）、**Open at Login** をオフにしてから、アプリを削除します。

## コマンドライン

```bash
uv tool install --python 3.13 agents-chronicle   # puts `chronicle` on PATH (~/.local/bin)
chronicle sync                                   # archive + ingest everything now
chronicle install                                # hooks, background agents, MCP server
chronicle connect codex                          # optional: codex, copilot, bob (see Sources)
```

[uv](https://docs.astral.sh/uv/) が必要です（`pipx install agents-chronicle` でも可）。リポジトリのチェックアウトから
インストールする場合は、その中で `uv tool install --python 3.13 .` を実行します。`chronicle install` は次の 4 つを行います
（それぞれ `--no-hooks`、`--no-launchd`、`--no-ui`、`--no-mcp` で省略でき、`--dry-run` で事前確認できます）：

| 構成要素 | 役割 |
| --- | --- |
| `~/.claude/settings.json` の `SessionEnd` フック | 終了したトランスクリプトを、アーカイブ・取り込み・分析を行う切り離されたプロセスに渡します。フック自体は数ミリ秒で戻ります。`settings.json` のバックアップは `~/.claude-chronicle/backups/` に保存されます。 |
| launchd `com.claude-chronicle.sync` | 15 分ごとに `chronicle sync --work` を実行します。フックが取りこぼしたものの回収、分析キューの処理、ナレッジベースの統合、ノートの書き出しを行います。 |
| launchd `com.claude-chronicle.ui` | ダッシュボードを <http://127.0.0.1:8765/> で常時提供します。 |
| MCP サーバー `chronicle`（ユーザースコープ） | Claude Code が過去のセッションとナレッジを検索できるようにします。 |

任意：`chronicle install --inject-context` を使うと、新しいセッションにそのプロジェクトのナレッジベースの短い要約を渡す
`SessionStart` フックも追加されます（既定ではオフ。内容は `chronicle context` で確認できます）。

すべてを削除するには `chronicle uninstall` を実行します（データは残ります。`--purge` でデータも削除）。

コマンドライン版からデスクトップアプリを使うには、`app` エクストラを追加して `chronicle app` を実行します：
`uv tool install --python 3.13 'agents-chronicle[app]'`。今後アプリだけを使う場合は、先に `chronicle uninstall` を実行してから
アプリで Claude Code を接続してください。launchd エージェントとアプリが並行して動くのを避けるためです（害はありませんが無駄です）。

## アップデート

**設定 › Status › Updates** に Chronicle のインストール方法が表示され、同じ方法でアップデートできます。

| インストール方法 | アップデートボタンが実行するもの |
| --- | --- |
| `uv tool install agents-chronicle` | **Check for updates** で新しいリリースが見つかったあと、`uv tool upgrade agents-chronicle` |
| `uv tool install .`（チェックアウトから） | インストール後にチェックアウトのファイルが変わったとき、`uv tool upgrade --reinstall agents-chronicle`（ネットワーク確認なし） |
| `pipx` または `pip` | `pipx upgrade agents-chronicle` または `pip install --upgrade agents-chronicle` |
| デスクトップアプリ | 実行しません。**Download** で最新リリースを開き、アプリケーションフォルダにドラッグします |

ネットワークに接続するのは **Check for updates**（pypi.org）だけです。同じカードの **Check for updates daily** をオンにすると、ダッシュボードを開いている間 1 日 1 回確認します。最後の結果は再起動後も残ります。アップデートが見つかると通知が表示され（リリースごと、チェックアウトなら新しいコミットごとに 1 回。**Later** で閉じられます）、Settings にドットが付き、ステータスバーに **Update to …** が出ます。チェックアウトの Updates カードには、再インストールで入るコミットと変更ファイルが並びます。
`chronicle ui`（またはその launchd エージェント）で動くダッシュボードはアップデート後に自動で再起動し、開いているタブも再読み込みされます。
コマンドラインの `chronicle app` は終了して開き直してください。同期や分析の実行中は、終わるまでボタンは待ちます。
ターミナルからは同じコマンドを直接実行できます。

うまく動かない場合は、[トラブルシューティング](troubleshooting.md)を参照してください。
