# インストール

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

Chronicle は macOS で動作し、分析を行うためにログイン済みの [Claude Code](https://claude.com/claude-code)（`claude`）または [Codex](https://github.com/openai/codex)（`codex`）が必要です。セットアップは Claude Code がインストールされていればそれを使い、なければ Codex を提案します。**ステータス › 分析**（Status › Analysis）または `chronicle config set analysis.backend codex` でいつでも切り替えられます。使い方は 2 通りあり、どちらも `~/.claude-chronicle` の同じデータを使うため、併用できます。

## デスクトップアプリ

1. [最新リリース](https://github.com/Chatixia-AI/agents-chronicle/releases/latest)から
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

Codex、Copilot、Bob、Antigravity はダッシュボードの**ソース**（Sources）ページから接続します。フックと MCP の登録は
`~/.claude-chronicle/bin/chronicle` を指しています。これはアプリが起動のたびに書き直す小さなスクリプトなので、
アプリを移動・更新しても壊れません。アプリを終了すると、次に起動するまで同期は止まります。終了で中断された分析は、
次の同期で改めて実行されます。

Chronicle を削除するには、`~/.claude-chronicle/bin/chronicle uninstall` を実行し（フックと MCP
サーバーを削除。データは残ります）、**Open at Login** をオフにしてから、アプリを削除します。

## コマンドライン

```bash
uv tool install --python 3.13 agents-chronicle   # puts `chronicle` on PATH (~/.local/bin)
chronicle install                                # pick the agents to record, import, start the dashboard
```

[uv](https://docs.astral.sh/uv/) が必要です（`pipx install agents-chronicle` でも可）。リポジトリのチェックアウトから
インストールする場合は、その中で `uv tool install --python 3.13 .` を実行します。

`chronicle install`（`chronicle setup` でも可）は次の順にセットアップします：

1. セッションを分析するエージェント（既定は Claude Code）を確認します。見つからず Codex がインストールされていれば、Codex で分析するか尋ねます。どちらもなければ、セッションは記録されますが、どちらかをインストールするまで分析されません。
2. この Mac にあるコーディングエージェント（Claude Code、Codex、GitHub Copilot、IBM Bob、Google Antigravity）と、MCP のみのクライアント
   （Claude Desktop、Cursor、Windsurf、Gemini CLI）を、ディスク上のセッション数とともに一覧にします。
3. 見つかってまだ接続していないものごとに、記録するか（既定は「はい」）、MCP クライアントには Chronicle のツールを
   渡すかを尋ねます。Codex Cloud はオンラインにアクセスするため、Codex の後に尋ね、既定は「いいえ」です。
   Claude Code を断ると `~/.claude` もスキャンしません。
4. 選んだものを `chronicle connect <name>` と同じ方法で接続し（[ソース](sources.md)）、過去のセッションを取り込みます
   （`--no-sync` で省略可。その場合はバックグラウンド同期が取り込みます）。
5. Chronicle をバックグラウンドで、ログイン時から動かすかを尋ねます（既定は「はい」）：下の 15 分ごとの同期と常時稼働の
   ダッシュボードです。「いいえ」の場合も Claude Code のセッションは終了時に記録・分析されます。それ以外は
   `chronicle sync --work`、ダッシュボードは `chronicle ui --open` で。エージェントが動いていれば以後は尋ねません（`--no-launchd --no-ui` でオフ）。
   バックグラウンド同期がオンなら、Chronicle の新しいバージョンが出たときにデスクトップ通知を表示するかも一度だけ
   尋ねます（`--notify-updates` または `--no-notify-updates` を付けると尋ねません）。
6. 分析について説明します：過去のセッションは Claude Code（または Codex）のログインで読み込まれ（プランの使用量に
   含まれます）、そこから得た知識で各プロジェクトのナレッジベース、次に**用語集**、次に**マップ**が作られます。
   セッションが分析されるまで、この 2 つは空のままです。待っているセッション数と、バックグラウンドで（15 分ごとに
   6 件）すべて終わるまでの目安を示し、今すぐ分析するかを尋ねます。段階ごと（セッション、ナレッジベース、用語集、
   マップのテーマ）に進捗バーを表示します。すべてか、最初の用語集とマップを数分で作れる新しい 20 件を選べます。
   Ctrl-C で止めても終わった分は残り、残りはバックグラウンドで分析されます。`--analyze all`、`--analyze N`
   （新しい N 件）、`--analyze later` を付けると尋ねません。
7. ダッシュボードのアドレスを表示します。初回は開くかどうか尋ねます。

端末がない場合や `--yes` を付けた場合は、尋ねずに既定値を使います（分析は後で）。何度実行しても安全です：接続済みのエージェントは
質問なしで更新されるので、尋ねるのはその後にインストールされたエージェントだけです。`--dry-run` は何をするかを表示し、何も変更しません。

Claude Code と Mac 本体には、次の 4 つを設定します（それぞれ `--no-hooks`、`--no-launchd`、`--no-ui`、`--no-mcp` で省略できます）。
`--no-launchd` と `--no-ui` は、そのエージェントがインストール済みなら削除もするので、`chronicle install --no-launchd --no-ui`
でバックグラウンド実行だけをオフにできます：

| 構成要素 | 役割 |
| --- | --- |
| `~/.claude/settings.json` の `SessionEnd` フック | 終了したトランスクリプトを、アーカイブ・取り込み・分析を行う切り離されたプロセスに渡します。フック自体は数ミリ秒で戻ります。`settings.json` のバックアップは `~/.claude-chronicle/backups/` に保存されます。 |
| launchd `com.claude-chronicle.sync` | 15 分ごとに `chronicle sync --work` を実行します。フックが取りこぼしたものの回収、分析キューの処理、ナレッジベースの統合、ノートの書き出しを行います。 |
| launchd `com.claude-chronicle.ui` | ダッシュボードを <http://127.0.0.1:8765/> で常時提供します。 |
| MCP サーバー `chronicle`（ユーザースコープ） | Claude Code が過去のセッションとナレッジを検索できるようにします。 |

任意：`chronicle install --inject-context` を使うと、新しいセッションにそのプロジェクトのナレッジベースの短い要約を渡す
`SessionStart` フックも追加されます（既定ではオフ。内容は `chronicle context` で確認できます）。

任意：`chronicle install --statusline` を使うと、Claude Code の各セッションが実際に使ったコンテキストと、Pro と Max プランでは
そのセッションの間に 5 時間枠と 7 日枠の上限がどれだけ進んだかを記録します（Claude Code はこれらをステータスラインにしか渡しません）。
`~/.claude/settings.json` の `statusLine` を `chronicle statusline` に設定し、これがスナップショットを `~/.claude-chronicle/statusline/`
に保存してから、もともと使っていたステータスラインを同じ入力で実行するため、表示は以前と変わりません。元の設定は
`~/.claude-chronicle/statusline/wrapped.json` に保存されます。ステータスラインを使っていなかった場合はモデル、コンテキスト、
上限を表示し、Claude Code はフッターのキー操作のヒントの大半を表示しなくなります。同期のたびに各セッションの数値がデータベースに
取り込まれます（セッションのページと**ステータス**）。`chronicle uninstall` で元のステータスラインに戻ります。

すべてを削除するには `chronicle uninstall` を実行します（データは残ります。`--purge` でデータも削除）。`--statusline` で
ステータスラインを包んでいた場合は、元のステータスラインも復元します。

コマンドライン版からデスクトップアプリを使うには、`app` エクストラを追加して `chronicle app` を実行します：
`uv tool install --python 3.13 'agents-chronicle[app]'`。今後アプリだけを使う場合は、先に `chronicle uninstall` を実行してから
アプリで Claude Code を接続してください。launchd エージェントとアプリが並行して動くのを避けるためです（害はありませんが無駄です）。

## アップデート

**設定 › ステータス › アップデート**（Settings › Status › Updates）に Chronicle のインストール方法が表示され、同じ方法でアップデートできます。

| インストール方法 | アップデートボタンが実行するもの |
| --- | --- |
| `uv tool install agents-chronicle` | **アップデートを確認**（Check for updates）で新しいリリースが見つかったあと、`uv tool upgrade agents-chronicle` |
| `uv tool install .`（チェックアウトから） | インストール後にチェックアウトのファイルが変わったとき、`uv tool upgrade --reinstall agents-chronicle`（ネットワーク確認なし） |
| `pipx` または `pip` | `pipx upgrade agents-chronicle` または `pip install --upgrade agents-chronicle` |
| デスクトップアプリ | 実行しません。**… をダウンロード**（Download …）で最新リリースを開き、アプリケーションフォルダにドラッグします |

ネットワークに接続するのは**アップデートを確認**（pypi.org）だけです。同じカードの**毎日アップデートを確認**（Check for updates daily）をオンにすると、ダッシュボードを開いている間 1 日 1 回確認します。**新しいバージョンを通知**（Notify me about new versions。`chronicle install` でも尋ねます）をオンにすると、ダッシュボードを開いていなくてもバックグラウンド同期が 1 日 1 回確認し、リリースごとに 1 回、アップデート方法を書いたデスクトップ通知を表示します（macOS は通知センター、Linux は `notify-send`）。macOS では通知を Chronicle の代わりに Script Editor が出すため、クリックすると Script Editor が開きます。アップデート先は通知の本文に書かれています。最後の結果は再起動後も残ります。アップデートが見つかると通知が表示され（リリースごと、チェックアウトなら新しいコミットごとに 1 回。**後で**（Later）を押すと閉じられます）、設定にドットが付き、ステータスバーに **… にアップデート**（Update to …）が出ます。チェックアウトの場合、アップデートのカードには、再インストールで入るコミットと変更ファイルが並びます。
`chronicle ui`（またはその launchd エージェント）で動くダッシュボードはアップデート後に自動で再起動し、開いているタブも再読み込みされます。
コマンドラインの `chronicle app` は終了して開き直してください。同期や分析の実行中は、終わるまでボタンは待ちます。
ターミナルからは同じコマンドを直接実行できます。

うまく動かない場合は、[トラブルシューティング](troubleshooting.md)を参照してください。
