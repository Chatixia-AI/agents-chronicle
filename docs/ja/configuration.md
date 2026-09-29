# 設定

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

設定は `~/.claude-chronicle/config.toml` にあります。`chronicle config` で表示し、`chronicle config edit` でファイルを開きます。
変更は次の同期またはワーカーの実行時に反映されます。`CHRONICLE_HOME` で保存先全体を移動できます。

## `[sources]`

| キー | 既定値 | |
| --- | --- | --- |
| `claude_dirs` | `["~/.claude"]` | 読み込む Claude Code の設定ディレクトリ。複数指定できます |
| `codex_dirs` | `[]` | Codex を接続すると `["~/.codex"]` |
| `copilot_dirs` | `[]` | Copilot を接続すると `~/.copilot` と VS Code の `User` ディレクトリ |
| `bob_dirs` | `[]` | Bob を接続すると `["~/.bob"]` |
| `import_history` | `true` | Claude Code がすでに削除したセッションのプロンプトを `history.jsonl` から復元する |
| `import_memory` | `true` | Claude の自動メモリーノート（`projects/*/memory/*.md`）をナレッジとして取り込む |
| `exclude_projects` | `[]` | 完全に無視するプロジェクトパスの glob パターン。例：`["/Users/me/secret/*"]` |

## `[analysis]`

| キー | 既定値 | |
| --- | --- | --- |
| `auto` | `true` | アイドルになったセッションを自動で分析する |
| `model` / `effort` | `sonnet` / `medium` | `claude --model` の任意のエイリアス |
| `max_budget_usd` | `3.0` | `claude -p` の呼び出し 1 回あたりの費用上限（API 換算の USD） |
| `idle_minutes` | `20` | 分析されるには、セッションが終了しているか、この時間アイドルである必要があります |
| `min_prompts` | `1` | 人間のプロンプトがこれより少ないセッションはスキップされます |
| `max_per_run` / `concurrency` | `6` / `2` | 15 分ごとの実行 1 回あたりの分析数と、並列に動かす `claude -p` のプロセス数 |
| `backfill` | `true` | インストール前に記録されたセッションも分析する（新しい順） |
| `chunk_chars` | `150000` | 1 回の呼び出しに渡す、まとめたトランスクリプトの文字数。これより長いセッションは map-reduce で処理します |
| `timeout_seconds` | `900` | 呼び出し 1 回あたりの実時間の上限 |
| `claude_bin` | `""` | `claude` のパス（空の場合は自動で検出） |

## `[synthesis]`、`[export]`、`[server]`、`[inject]`

| キー | 既定値 | |
| --- | --- | --- |
| `synthesis.auto` / `model` / `min_new_items` | `true` / `sonnet` / `3` | 新しい項目がこの件数たまると、プロジェクトのナレッジベースを再構築する |
| `export.markdown` | `true` | すべてを Markdown 保管庫にミラーする |
| `export.notes_dir` | `""` | 保管庫の場所（空の場合：`~/.claude-chronicle/notes`） |
| `server.host` / `port` | `127.0.0.1` / `8765` | ダッシュボード。このポートが使用中の場合、アプリは空いているポートを使います |
| `inject.session_start` / `max_chars` | `false` / `3000` | 新しいセッションにプロジェクトのナレッジベースの要約を渡す（SessionStart フック） |
