# ソース：Claude Code、Codex、GitHub Copilot、IBM Bob

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

`chronicle sources`（またはダッシュボードの **Sources** タブ）で、各コーディングエージェントについて次の情報を確認できます：
検出されたかどうか、バージョン、ディスク上のセッション数と記録・分析済みの数、記録方法、フックと MCP サーバーが設定されているか。
接続と切断はダッシュボード、または `chronicle connect <agent>` / `chronicle disconnect <agent>` で行います
（`claude`、`codex`、`codex-cloud`、`copilot`、`bob`。記録済みのセッションは常に残ります）。どのソースも同じセッションモデルに変換されるため、
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

**Codex Cloud**（chatgpt.com/codex のタスク）は、ネットワークに接続するため別に接続します（`chronicle connect codex-cloud`）。
同期のたびに Codex のログイン（`codex login`）で `codex cloud list` を実行し、新しいタスクや変わったタスクには `codex cloud diff` を実行します。
各タスクは Codex のセッション（`source = codex-cloud`）になり、タイトル、リポジトリ、状態、変更ファイルと行数、差分、タスクへのリンクが入ります。
リポジトリ名がローカルのプロジェクトと一致すれば、そのプロジェクトにまとまります。Codex CLI はクラウドタスクの会話を返さないため、
これらのセッションにはプロンプトがなく、分析もされません。タスクと差分は `~/.claude-chronicle/archive/codex-cloud/` にアーカイブされ、
クラウド側でタスクが消えても残ります。一覧の取得に失敗した場合（未ログイン、オフライン）は Sources のカードに理由が出て、次の同期で再試行します。

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

**claude.ai と ChatGPT のチャット**は Mac に保存されないため、データのエクスポートから取り込みます。claude.ai は
**設定 › プライバシー › データをエクスポート**、ChatGPT は **設定 › データコントロール › データをエクスポート** を開くと、届いたメールのリンクから
`.zip` をダウンロードできます。Sources ページの **Import export…**（カード *Chat exports*）、または `chronicle import <zip>` で取り込みます
（展開したフォルダーや `conversations.json` も使えます）。どちらのサービスのものかは中身から判別します。各チャットはセッション（エージェント
`claude-ai` または `chatgpt`、`source = claude-ai-export` または `chatgpt-export`）になり、プロンプト、応答、思考、ツール呼び出し
（claude.ai のアーティファクト、ChatGPT の Python・ブラウズ・画像生成とその出力）、添付ファイルや画像の注記が入ります。claude.ai のプロジェクト内の
チャットは `claude.ai/<プロジェクト>`、それ以外は `claude.ai`、ChatGPT のチャットは `chatgpt.com` にまとまります。ChatGPT のチャットは画面に表示される
分岐に沿って読むため、編集前のプロンプトや再生成で切り替えた回答は含まれません。新しいエクスポートはいつでも取り込めます。新しいチャットと
変更されたチャットだけが追加されます。読み込んでアーカイブするのはチャット（`conversations.json` と、プロジェクト名のための claude.ai の
`projects.json`）だけで、アカウントのファイル（`users.json`、`user.json`）と ChatGPT の `chat.html` は開きません。
ダッシュボードからアップロードした zip は取り込み後に削除します。取り込んだチャットは**自動では分析しません**（何年分ものチャットを分析すると
プランの上限を一度に使い切るため）。Sessions の一覧で分析したいチャットにチェックを入れて **Analyze** を選ぶ（**Select all matching** でフィルターに合うチャットをすべて選べます）か、チャットを開いて **Analyze now** を選びます。`--analyze` を付けて取り込むとすべて分析待ちに入ります。
エクスポートにはトークン数がないため、費用は表示されません。Claude Code on the web のセッションは claude.ai のエクスポートに含まれません。
`claude --teleport <id>` で Mac に通常の Claude Code のトランスクリプトとして取り込めます。

Claude Desktop、Cursor、Windsurf、Gemini CLI は記録しませんが、MCP サーバーは使えます。[MCP サーバー](mcp.md)を参照してください。
