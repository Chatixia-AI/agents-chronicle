# ソース：Claude Code、Codex、GitHub Copilot、IBM Bob

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

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
