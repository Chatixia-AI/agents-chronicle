# Claude Chronicle

[English](README.md) | 日本語

このマシン上のコーディングエージェントのセッション（Claude Code、接続すれば OpenAI Codex、GitHub Copilot、IBM Bob も）を
すべてローカルの保管庫に記録し、元のトランスクリプトを無期限に保存します。さらに Claude Code 自身（ヘッドレスの
`claude -p`）を使って、各セッションを概要と再利用できるナレッジに変換します。記録した内容は、ローカルのダッシュボード、
Obsidian 互換の Markdown 保管庫、CLI、そして MCP サーバー経由でエージェント自身の中から閲覧できます。

![Chronicle の仕組み：ソース、アーカイブ、解析、SQLite、claude -p による分析、ナレッジ、そしてダッシュボード・保管庫・CLI・MCP サーバー](docs/diagrams/architecture.excalidraw.svg)

## なぜ必要か

- **Claude Code は 30 日でトランスクリプトを削除します**（`cleanupPeriodDays`）。Chronicle は `~/.claude/projects`
  配下のファイルをすべて `~/.claude-chronicle/archive` にミラーし（JSONL は gzip 圧縮）、削除しません。
  トランスクリプトがすでに消えていたセッションも、`~/.claude/history.jsonl` から一部を復元します
  （プロンプトのみ。*history* として表示）。
- **ナレッジは消えていきます。** セッション中に見つかった修正方法、落とし穴、設計判断、プロジェクトの事実を抽出し、
  プロジェクトごとに重複を除いて検索できるようにします。後のセッションで Claude 自身が検索することもできます。

## インストール

Chronicle は macOS で動作し、分析のためにログイン済みの [Claude Code](https://claude.com/claude-code)（`claude`）が必要です。
使い方は 2 通りあり、どちらも `~/.claude-chronicle` の同じデータを使うため、併用できます。

### デスクトップアプリ

1. [最新リリース](https://github.com/kayeungadrian-tam/agents-chronicle/releases/latest)から
   `Chronicle-<version>-arm64.dmg` をダウンロードします（Apple シリコン、macOS 13 以降）。
2. DMG を開いて **Chronicle** を「アプリケーション」フォルダにドラッグし、そこから起動します。
3. 初回起動時に **Connect** を選ぶと、Claude Code のセッションの記録が始まります。`SessionEnd` フックと MCP サーバーが
   追加され（`chronicle connect claude` と同じ）、Chronicle がログイン時に起動するようになります。

macOS に「“Chronicle”は開けません」や「開発元を検証できません」と表示された場合、そのリリースは公証されていません。
**システム設定 → プライバシーとセキュリティ** を開き、Chronicle のメッセージの横にある **このまま開く** をクリックして確認してください。
Intel 版はまだありません。Intel Mac ではコマンドラインでインストールしてください。

以降、Chronicle はメニューバーに常駐します。ダッシュボードを専用ウインドウで表示し、15 分ごとのバックグラウンド同期も
アプリ自身が行うため、launchd エージェントは不要です。ウインドウを閉じても動き続けます。メニューバーアイコンの項目：

| メニュー項目 | |
| --- | --- |
| Open Chronicle / Open in Browser | ダッシュボードをアプリのウインドウ、またはブラウザで開く |
| Sync Now | 次の 15 分ごとの実行を待たずに、今すぐアーカイブ・取り込み・分析を行う。すぐ上の行に最終同期時刻を表示 |
| Connect Claude Code… | Claude Code が未接続のときに表示（初回起動時に *Not Now* を選んだ場合） |
| Open at Login | 接続後はオン。オフにすると、自分で開いたときだけ Chronicle が動きます |
| Install Command-Line Tool | アプリ内蔵の `chronicle` コマンドを `~/.local/bin` にリンク（既に存在する場合は何もしません） |
| Open Data Folder | `~/.claude-chronicle` を開く |

Codex、Copilot、Bob はダッシュボードの **Sources** ページから接続します。フックと MCP の登録は
`~/.claude-chronicle/bin/chronicle` を指しています。これはアプリが起動のたびに書き直す小さなスクリプトなので、
アプリを移動・更新しても壊れません。アプリを終了すると、次に起動するまで同期は止まります。終了で中断された分析は、
次の同期で改めて実行されます。

コマンドライン版を入れずにアプリだけを使う場合の既知の問題：

- ダッシュボードの **Status** ページと **Sources** ページ、および `chronicle status` は、launchd エージェントしか確認しないため、
  *Background sync* が停止中と表示されます。実際にはアプリ自身の同期が動いています。最終同期時刻はメニューバーのメニューで確認できます。
- `analysis.backfill = false` が効きません。アプリの Connect は、`chronicle install` が記録するインストール日を記録しないため、
  接続前のセッションも分析されます。この設定を有効にするには、`~/.claude-chronicle/bin/chronicle install --no-launchd --no-ui`
  を一度実行してください。インストール日が記録され、フックと MCP サーバーが再登録されます。

Chronicle を削除するには、`~/.claude-chronicle/bin/chronicle uninstall` を実行し（フックと MCP サーバーを削除。データは残ります）、
**Open at Login** をオフにしてから、アプリを削除します。

### コマンドライン

```bash
uv tool install --python 3.13 agents-chronicle   # `chronicle` を PATH に追加（~/.local/bin）
chronicle sync                                   # 今すぐすべてをアーカイブして取り込む
chronicle install                                # フック、バックグラウンドエージェント、MCP サーバー
chronicle connect codex                          # 任意：codex、copilot、bob（「ソース」を参照）
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

## ソース：Claude Code、Codex、GitHub Copilot、IBM Bob

`chronicle sources`（またはダッシュボードの **Sources** タブ）で、各コーディングエージェントについて次の情報を確認できます：
検出されたかどうか、バージョン、ディスク上のセッション数と記録・分析済みの数、記録方法、フックと MCP サーバーが設定されているか。
接続と切断はダッシュボード、または `chronicle connect <agent>` / `chronicle disconnect <agent>` で行います
（`claude`、`codex`、`copilot`、`bob`。記録済みのセッションは常に残ります）。どのソースも同じセッションモデルに変換されるため、
すべてのエージェントのセッションがダッシュボード、分析、ナレッジベース、用語集、MCP ツールを共有します。

**Codex**（`~/.codex`）は任意で接続します。接続すると：

- 設定ファイルに `sources.codex_dirs` を記録し、`~/.codex/sessions`（ロールアウト）、`session_index.jsonl`、Codex 自身の
  メモリーノートをアーカイブします。ロールアウトは同じセッションモデルに変換されます：プロンプト（IDE コンテキストの外枠は外します）、
  応答、ツール呼び出し（`exec_command`、`apply_patch`、`write_stdin`、Web、MCP、サブエージェント。コードモードの `exec` スクリプトは
  呼び出したツール名で表示）、ファイル編集（`FileChange` 項目またはパッチ）、実際の終了コード（結果チャンク、`CommandExecution` 項目、
  `wait` で完了した長時間実行セル）、応答ごとのトークン使用量、コンパクション、中断。
- Codex に MCP サーバーを登録します（`codex mcp add chronicle`）。これで Codex も、Claude のものを含むすべてのセッションを検索できます。
- Codex Desktop が取り込んだ **Claude Code のセッションを復元します**：Claude Code が元のトランスクリプトをすでに削除していた場合、
  Codex 側のコピーが完全なセッションになります（`source = codex-import`）。重複はスキップされます。

Codex にはセッション終了フックがなく（唯一の `notify` 枠も他のアプリが使っている場合があります）、Codex のセッションはアイドルになった後、
15 分ごとのバックグラウンド同期で取り込まれます。GPT のトークン費用は OpenAI の定価で計算し、価格が公開されていない新しい GPT モデルは
GPT-5 の料金で見積もります。

**GitHub Copilot** は任意で接続します（`chronicle connect copilot`）。2 つの保存先を記録します：

- `~/.copilot/session-state/<id>/events.jsonl` の Copilot エージェントセッション（Copilot CLI と VS Code の Copilot エージェントホスト）：
  プロンプト、応答、推論、結果と所要時間付きのツール呼び出し、行数の合計。呼び出しごとのトークン使用量（キャッシュの内訳付き）は
  `~/.copilot/session-store.db` から取得し、SQLite のスナップショットとしてアーカイブします。
- VS Code の Copilot Chat：`User/workspaceStorage/<hash>/chatSessions/*.jsonl`。各ファイルはパッチのログで、最終的なチャットに再生されます。
  エージェントループからツール呼び出し、結果、編集が得られ、空のチャットパネルはスキップされます。これらのログはキャッシュ済みの入力と
  それ以外を区別しないため、トークン数はありますが費用の見積もりはありません。

接続すると、VS Code（`User/mcp.json`）と Copilot CLI（`~/.copilot/mcp-config.json`）にも MCP サーバーが登録されます。
どちらのファイルも事前に `~/.claude-chronicle/backups/` にバックアップされ、ファイル内の他のサーバー設定はそのまま残ります。

**IBM Bob** は任意で接続します（`chronicle connect bob`）。`~/.bob/db/bob.db` からタスクとメッセージを読み取り専用で読み込み、
そのデータベースの SQLite スナップショットをアーカイブします。`~/.bob` 内のそれ以外（ログイン状態など）は読みません。
Bob IDE は会話ファイルをローカルに保存しないため、記録されるのはこのデータベース内のタスクだけです。接続すると
`~/.bob/settings/mcp_settings.json` に MCP サーバーが登録されます。

## 使い方

| コマンド | |
| --- | --- |
| `chronicle app` | デスクトップアプリ（ウインドウ＋メニューバー）。`app` エクストラが必要 |
| `chronicle ui [--open]` | ダッシュボード（インストール後は :8765 で常時稼働）。Sessions、Knowledge、Projects、Glossary は Cards と List（並べ替え可能な表。行をクリックで詳細）を切り替えられ、ページごとに記憶されます |
| `chronicle sessions [-p project] [--since 7d]` | セッションの一覧 |
| `chronicle show <id-prefix> [--transcript\|--markdown\|--json]` | セッションの概要、または会話全体 |
| `chronicle search <words>` | トランスクリプトとナレッジの全文検索（言語を問わず、3 文字以上） |
| `chronicle knowledge [query] [-k gotcha] [-p project]` | 抽出されたナレッジの閲覧 |
| `chronicle projects` / `chronicle stats [--since 30d]` | プロジェクト別と全体の統計 |
| `chronicle analyze <id> \| --pending [--limit N] [--dry-run]` | 今すぐ分析（`--dry-run` は要約のサイズを表示するだけで、トークンを使いません） |
| `chronicle synthesize [--project P] [--global] [--all]` | ナレッジベースを再構築 |
| `chronicle export [--full]` | Markdown 保管庫を書き直す |
| `chronicle glossary [term] [-p project] [--rebuild --all] [--themes]` | あなたの語彙：社内名称、略語、業務用語と、その定義と使われ方。`--themes` で大きいカテゴリをマップ用のテーマに分けます |
| `chronicle review [2026-W39\|current]` | Claude が書く週次の振り返り（週が終わるたびに自動作成） |
| `chronicle forget <id> [--delete-transcript]` | セッションを保管庫から完全に削除（再取り込みされません） |
| `chronicle sources` | 接続中のエージェントと、その記録方法 |
| `chronicle connect <agent>` / `disconnect <agent>` | `claude`、`codex`、`copilot`、`bob` の記録を開始／停止（データは残ります） |
| `chronicle status` | 状態確認：フック、エージェント、MCP、キュー、失敗 |
| `chronicle config [edit]` | `~/.claude-chronicle/config.toml` を表示または編集 |

**ダッシュボード：** 概要（稼働時間の見出しと稼働日数・最長連続日数、スパークライン付きの統計タイル（比較できる前の期間がそろうまでは
1 日あたりの値）、7 日平均付きの日次グラフ、結果の内訳、連続記録付きのアクティビティカレンダー、最も忙しい時間帯、プロジェクト、
失敗した呼び出しを含むツール、モデル、エージェント）、並べ替え・絞り込みできるセッション一覧、12 週間の活動を示すプロジェクトカード、
セッションページ（要約、ナレッジ、コンパクションを含むコンテキストウインドウのグラフ、ツール、ファイル、サブエージェント、PR、
折りたためるツール呼び出しとサブエージェントのスレッドを含むトランスクリプト全体の再生）、ナレッジブラウザー（ピン留め／却下）、
プロジェクトのナレッジベース、グローバルプレイブック、用語集、用語集のマインドマップ（後述の「マップ」）、週次の振り返り、
メッセージに直接飛べる検索。用語集の用語は、表示される場所（トランスクリプト、ナレッジ、要約）ではどこでも下線付きになり、
ホバーで定義、クリックで項目を表示します。すべてのグラフに表形式の表示があり、ライトとダークのテーマに対応しています。

**Markdown 保管庫：** `~/.claude-chronicle/notes`（Obsidian の保管庫として開けます）：`Home.md`、YAML フロントマター付きの
`Sessions/YYYY/MM/*.md`、`Projects/*.md`（ナレッジベース＋セッション一覧）、`Knowledge/<Kind>.md`、`Reviews/YYYY-Www.md`、
`Glossary.md`、`Global Playbook.md`。

**エージェントの中から**（MCP ツール。Claude Code と接続済みの各エージェントに登録）：`search_knowledge`、`search_sessions`、
`get_session`、`get_transcript`、`project_knowledge`、`glossary`、`recent_sessions`。たとえば *「このエラー、前にも出た？」* や
*「deployer_ip のルールって何だっけ？」* のように尋ねられます。

**用語集：** 生のトランスクリプトではなく、各プロジェクトから抽出されたナレッジをもとに Claude が作成します。プロジェクトごとに 1 回の
呼び出しと、プロジェクト横断の 1 回の処理で作られ、プロジェクトのナレッジベースが再統合されるたびに更新されます。各用語には、
カテゴリ、別名（略語や日本語の業務用語の訳など）、定義、プロジェクトごとの使われ方、関連用語、全文検索による統計（言及したセッション数、
最初と最後に見た日、言及の多いセッション）があります。

**マップ：** ダッシュボードの **Map** ページは、用語集を折りたためるマインドマップとして描きます。マップ左上の **Group by** で、
**Category**（カテゴリ）、**Theme**（テーマ）、**Project**（プロジェクト）、**Agent**（その用語を学んだセッションのエージェント）の
4 つの階層を好きな順に重ねられ、最後に用語が並びます。サイドパネルの **Views** には、よく使う組み合わせ（Category › Theme、
Project › Category › Theme、Category › Project、Agent › Category › Theme）があります。用語を開くと、その元になったナレッジ項目と、
その用語に最も多く言及したセッションが表示されます。ノードをクリックすると開閉し、詳細を表示します：用語なら定義、各プロジェクトでの
使われ方、関連用語（クリックでその用語へ移動）、ナレッジとセッション。カテゴリならそのテーマ、テーマならその説明です。ドラッグまたは
スクロールで移動、ピンチまたは ⌘＋スクロールでズームします。**Find a term** で用語までの経路を開き、開いた枝が画面に収まるよう
表示が自動で移動します。色はカテゴリを表し（大きい 8 カテゴリは固有の色、それ以外は灰色。プロジェクトとエージェントの階層は無彩色）、
用語の点の大きさは言及したセッション数に応じて変わります（1、2〜4、5 以上）。ファイル名とコマンドは **Files & commands** をオンにするまで
非表示です。1 つの枝に描くのは最大 10 ノード（最上位は 12、用語はナレッジ最大 6 件とセッション最大 4 件）で、よく話題になったものから並び、
残りは *+N more* からサイドパネルで一覧できます。一覧は入力しながら絞り込め、選んだものだけがマップに追加されます（検索や関連用語の
リンクも同じ動きです）。用語集の各項目には、マップ上の位置へのリンク（*on the map →*）があります。

**テーマ：** 用語が 25 以上あるカテゴリは、Claude が 4〜10 個の名前付きテーマに分けます（例：concept →
「Cloud infra, auth & integrations」「Agent dev workflow & tooling」）。カテゴリごとに `claude -p` を 1 回呼び出すので、マップのどの階層も
長い一覧になりません。テーマは用語集の再構築後に、用語が変わったカテゴリだけ作り直されます。それまでに追加された用語は
*Not grouped yet* と表示されます。手動では `chronicle glossary --themes [--force]`、またはマップのサイドパネルの **Group with Claude**
ボタンで実行できます。用語数 1,360 の用語集では、大きい 10 カテゴリの合計が API 定価換算で約 $1.40 でした。

## 記録される内容

セッションごと：プロジェクト、ブランチ、Claude Code のバージョン、開始／終了、経過時間と実稼働時間（15 分を超えるアイドル時間は除外）、
人間のプロンプト（Claude の作業中にキューに入れたものを含む）、スラッシュコマンド、中断、コンパクション、所要時間と成否付きのすべての
ツール呼び出し、行数付きの読み込み・編集ファイル、固有の使用量を持つサブエージェントとワークフロー、スキル、MCP サーバー、フック、
PR と成果物、そして API 呼び出しごとのトークン使用量（メッセージ単位で重複除去）と API 定価による費用の見積もり。見積もりは、
単一プロセスのセッションでは Claude Code 自身の `cost-state` とセント単位で一致します。サブスクリプションの請求とは異なります。

分析済みのセッションごと：タイトル、要約、目的、結果、作業の種類、タグ、ハイライト、未解決の事項、つまずき、雰囲気、そしてナレッジ項目：

| 種類 | 意味 |
| --- | --- |
| fix | 失敗、その根本原因、修正方法 |
| gotcha | 落とし穴と、その避け方 |
| learning | 技術やコードベースについての気づき |
| decision | 設計上の判断と、その理由 |
| pattern | 再利用できる手法やスニペット |
| command | 役立つコマンドの使い方 |
| fact | プロジェクトの構成、設定、エンドポイント、デプロイ |
| preference | Claude にどう作業してほしいか |
| reference | 外部への参照 |
| todo | 後で対応すること |

Claude 自身の自動メモリーノート（`projects/*/memory/*.md`）と Codex のメモリーノートも、ナレッジとして取り込まれます。

Codex、Copilot、Bob のセッションも、ログにデータがある範囲で同じ項目を埋めます。たとえば Copilot Chat のログにはキャッシュの内訳がない
（そのため費用の見積もりもない）、Bob のタスクには呼び出しごとの所要時間がない、といった違いがあります。

## 分析の仕組み

![セッションがナレッジになるまで：キュー、要約、claude -p、JSON の検証、ナレッジ項目、ナレッジベース、用語集、週次の振り返り](docs/diagrams/analysis.excalidraw.svg)

1. セッションは、終了した時点（フック）か、`idle_minutes` の間アイドルになった時点でキューに入ります。
2. トランスクリプトは、`chunk_chars` に収まる範囲で最も詳しいレベルの要約にまとめられます（プロンプトと応答の全文、ツール呼び出しは 1 行ずつ、
   エラーの抜粋、サブエージェントの報告）。非常に長いセッションはプロンプトの境界で分割し、map-reduce で処理します。機密情報は最初に伏せ字にします。
3. `claude -p` は `--no-session-persistence --safe-mode --tools "" --strict-mcp-config` 付きで実行されます：分析そのものの
   トランスクリプトは書き出されず、フック・プラグイン・MCP は読み込まれず、モデルは回答することしかできません。
   これらの実行中は `CHRONICLE_INTERNAL=1` によってフックが無効になります。
4. JSON の応答は寛容に検証され（修復は 1 回まで）、保存されます。プロジェクトに `min_new_items` 件の新しい項目がたまると、
   そのプロジェクトのナレッジベースが再統合され、古くなった項目や重複した項目は *superseded*（置き換え済み）になります
   （ピン留めした項目とメモリー項目は置き換えられません）。終わった週のセッションがすべて分析されると、Claude がその週の振り返り
   （テーマ、成果、学び、未解決の事項、繰り返し起きたつまずき、作業の進め方への具体的な提案）を書きます。
5. 使用量の上限や認証のエラーが出ると、分析を 1 時間停止します。その他の失敗は 30 分 → 2 時間 → 8 時間と間隔を空けて再試行します。
   呼び出しには実時間の期限があり、Mac のスリープで止まった呼び出しは復帰直後に強制終了され、失敗としては数えずにキューに戻されます。
   分析後に続きが行われたセッションは、再び分析されます。

費用：分析はあなたの Claude Code のログインを通じて行われます。表示される費用は API 定価に換算した金額です。Sonnet ではセッションあたり
平均約 $0.38 でした（要約の平均は約 15 万文字）。Claude のサブスクリプションでは、請求ではなくプランの使用枠から消費されます。
`chronicle analyze --pending --dry-run` で未分析分の規模を確認でき、`max_budget_usd` で 1 回の呼び出しの上限を設定できます。

## 設定（`~/.claude-chronicle/config.toml`）

| キー | 既定値 | |
| --- | --- | --- |
| `sources.claude_dirs` | `["~/.claude"]` | 複数の Claude 設定ディレクトリに対応 |
| `sources.codex_dirs` | `[]` | Codex を接続すると `["~/.codex"]` |
| `sources.copilot_dirs` | `[]` | Copilot を接続すると `~/.copilot` と VS Code の `User` ディレクトリ |
| `sources.bob_dirs` | `[]` | Bob を接続すると `["~/.bob"]` |
| `sources.exclude_projects` | `[]` | 完全に無視するプロジェクトパスの glob パターン |
| `analysis.auto` | `true` | 自動で分析する |
| `analysis.model` / `effort` | `sonnet` / `medium` | `claude --model` の任意のエイリアス |
| `analysis.max_per_run` / `concurrency` | `6` / `2` | 15 分ごとの実行 1 回あたりの上限 |
| `analysis.backfill` | `true` | インストール前に記録されたセッションも分析する |
| `analysis.idle_minutes` | `20` | |
| `synthesis.auto` / `min_new_items` | `true` / `3` | |
| `export.markdown` / `notes_dir` | `true` / `~/.claude-chronicle/notes` | |
| `server.port` | `8765` | このポートが使用中の場合（launchd のダッシュボードなど）、アプリは空いているポートを使います |
| `inject.session_start` | `false` | 新しいセッションにナレッジの要約を渡す |

`CHRONICLE_HOME` で保存先全体を移動できます。

## データとプライバシー

すべてこのマシンに保存されます：`~/.claude-chronicle/{chronicle.db, archive/, notes/, logs/}`（アプリは、フックが呼び出す
起動スクリプト `bin/chronicle` と、ウインドウの保存領域 `webview/` を追加します）。外部に送られるのは伏せ字処理済みの要約だけで、
あなた自身の Claude Code を通じて Claude に送られます（トランスクリプトを生成したのと同じサービスです）。ダッシュボードは
127.0.0.1 にのみバインドし、外部の `Host` ヘッダーを拒否し（DNS リバインディング対策）、状態を変更するリクエストには
独自ヘッダーを必須にしています（CSRF 対策）。他のエージェントのデータは読み取るだけです（SQLite データベースは読み取り専用の接続で
読み込み、スナップショットとしてアーカイブします）。Bob のログイン状態は一切読みません。エージェントを接続するとその MCP 設定を
編集しますが、事前に `~/.claude-chronicle/backups/` にバックアップします。

## 開発

```bash
uv sync && uv run pytest -q        # 86 テスト、約 12 秒：偽の `claude` バイナリと、合成した Codex・Copilot・Bob のデータを使用
# 再デプロイ：uv はローカルビルドを pyproject.toml だけをキーにキャッシュするため、--reinstall が必要
uv tool install --force --reinstall --python 3.13 . && chronicle install   # install でエージェントも再起動
```

**macOS アプリ：** `uv run --extra app chronicle app` でチェックアウトから起動できます（Open at Login など、バンドルでしか意味のない
メニュー項目は非表示）。`./packaging/macos/build.sh` は `dist/Chronicle.app` と `dist/Chronicle-<version>-<arch>.dmg` をビルドします
（PyInstaller、約 30 秒。`packaging/macos/Chronicle.spec`）。1 つのバイナリが、引数なしではアプリとして、引数ありでは CLI として動き、
フックと MCP サーバーはこれを CLI として実行します。署名なしのビルドはアドホック署名となり、ビルドした Mac でのみ動きます。配布するには
`CHRONICLE_CODESIGN_IDENTITY`（Developer ID Application 証明書）と `NOTARY_KEYCHAIN_PROFILE`（`xcrun notarytool store-credentials`
で作成）を設定すると、スクリプトが DMG の署名・公証・ステープルまで行います。`packaging/macos/make_icon.py` でアイコンを再描画できます。
`desktop.py` は pywebview の Cocoa アプリデリゲートを拡張しているため、pywebview を `<7` に固定しています。

**リリース：** `pyproject.toml` の `version` を上げ、`v<version>` タグで GitHub リリースを公開します。
`.github/workflows/release.yml` がテストを実行し、`agents-chronicle` を PyPI に公開し（Trusted Publishing、環境 `pypi`）、
DMG をリリースに添付します（`MACOS_*` / `APPLE_*` シークレットが設定されていれば署名・公証済み。詳細はワークフローの先頭を参照）。
ワークフローを手動で実行すると（**Actions → Release → Run workflow**）ドライランになり、テストを実行して DMG をワークフローの
成果物として保存するだけで、何も公開しません。

最初のリリースの前に一度だけ必要な設定：

1. PyPI で *pending publisher* を追加します（Account → Publishing）：プロジェクト `agents-chronicle`、オーナー `kayeungadrian-tam`、
   リポジトリ `agents-chronicle`、ワークフロー `release.yml`、環境 `pypi`。
2. GitHub リポジトリで `pypi` という名前の環境を作成します（Settings → Environments）。
3. 署名・公証済みの DMG を配布するには（Apple Developer Program への加入が必要）：*Developer ID Application* 証明書を鍵ごと `.p12` として
   書き出し、シークレット `MACOS_CERT_P12`（ファイルの base64）、`MACOS_CERT_PASSWORD`、`MACOS_CODESIGN_IDENTITY`、`APPLE_ID`、
   `APPLE_TEAM_ID`、`APPLE_APP_PASSWORD`（account.apple.com で発行するアプリ用パスワード）を追加します。これらがない場合、DMG は
   アドホック署名となり、利用者は「プライバシーとセキュリティ」で許可する必要があります。

`docs/diagrams/` の図は `.excalidraw.svg` ファイルです。画像として表示され、Excalidraw の VS Code 拡張機能（`pomdtr.excalidraw-editor`）
または excalidraw.com で編集できます。保存すると同じファイルに書き戻されます。

構成：`parser.py`（Claude のトランスクリプト形式）、`codex_parser.py`（Codex のロールアウト）、`copilot_parser.py`（Copilot の
エージェントセッション＋VS Code のチャットログ）、`bob_parser.py`（Bob のタスク）、`agents.py`（エージェント名）、`connectors.py`（ソース）、
`ingest.py`（アーカイブ＋保存）、`digest.py` / `analyze.py` / `llm.py`（分析）、`synthesize.py`（ナレッジベース）、`glossary.py`、
`reviews.py`、`worker.py`（キュー）、`server.py` ＋ `web/`（ダッシュボード）、`mcp_server.py`、`export_md.py`、`hooks.py` / `install.py`、
`desktop.py`（macOS アプリ）、`cli.py`。`packaging/macos/` がアプリをビルドします。
