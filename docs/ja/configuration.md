# 設定

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

設定は `~/.claude-chronicle/config.toml` にあります。`chronicle config` で表示し、`chronicle config edit` でファイルを開きます。
変更は次の同期またはワーカーの実行時に反映されます。`CHRONICLE_HOME` で保存先全体を移動できます。

## `[sources]`

| キー | 既定値 | |
| --- | --- | --- |
| `claude_dirs` | `["~/.claude"]` | 読み込む Claude Code の設定ディレクトリ。複数指定できます |
| `codex_dirs` | `[]` | Codex を接続すると `["~/.codex"]` |
| `codex_cloud` | `false` | Codex Cloud を接続すると `true`。同期のたびに codex CLI でタスクを一覧します |
| `copilot_dirs` | `[]` | Copilot を接続すると `~/.copilot` と VS Code の `User` ディレクトリ |
| `bob_dirs` | `[]` | Bob を接続すると `["~/.bob"]` |
| `antigravity_dirs` | `[]` | Antigravity を接続すると `["~/.gemini/antigravity"]` |
| `import_history` | `true` | Claude Code がすでに削除したセッションのプロンプトを `history.jsonl` から復元する |
| `import_memory` | `true` | Claude の自動メモリーノート（`projects/*/memory/*.md`）をナレッジとして取り込む |
| `exclude_projects` | `[]` | 完全に無視するプロジェクトパスの glob パターン。例：`["/Users/me/secret/*"]` |

## `[analysis]`

| キー | 既定値 | |
| --- | --- | --- |
| `auto` | `true` | アイドルになったセッションを自動で分析する |
| `backend` | `claude` | セッションを分析するエージェント（あなた自身のログインを使用）：`claude`（Claude Code）または `codex`（Codex）。**Status › Analysis** でも変更できます |
| `model` / `effort` | `sonnet` / `medium` | Claude：`claude --model` の任意のエイリアス。`effort` は Codex の推論の強さにも使われます（`max` は `xhigh` になります） |
| `codex_model` | `""` | Codex のモデル。例：`gpt-5.5`。空の場合は Codex の既定のモデルを使います |
| `screen_model` | `haiku` | 取り込んだチャットを選別するモデル（`chronicle screen`）。各チャットの冒頭だけを、1 回の呼び出しで 60 件ずつ読みます |
| `max_budget_usd` | `3.0` | `claude -p` の呼び出し 1 回あたりの費用上限（API 換算の USD。Codex はトークン数だけを報告します） |
| `idle_minutes` | `20` | 分析されるには、セッションが終了しているか、この時間アイドルである必要があります |
| `min_prompts` | `1` | 人間のプロンプトがこれより少ないセッションはスキップされます |
| `max_per_run` / `concurrency` | `6` / `2` | 15 分ごとの実行 1 回あたりの分析数と、並列に動かす分析プロセスの数 |
| `backfill` | `true` | インストール前に記録されたセッションも分析する（新しい順） |
| `chunk_chars` | `150000` | 1 回の呼び出しに渡す、まとめたトランスクリプトの文字数。これより長いセッションは map-reduce で処理します |
| `timeout_seconds` | `900` | 呼び出し 1 回あたりの実時間の上限 |
| `claude_bin` / `codex_bin` | `""` | `claude` / `codex` のパス（空の場合は自動で検出） |

## `[synthesis]`、`[export]`、`[server]`、`[inject]`、`[updates]`

| キー | 既定値 | |
| --- | --- | --- |
| `synthesis.auto` / `model` / `min_new_items` | `true` / `sonnet` / `3` | 新しい項目がこの件数たまると、プロジェクトのナレッジベースを再構築する |
| `export.markdown` | `true` | すべてを Markdown 保管庫にミラーする |
| `export.notes_dir` | `""` | 保管庫の場所（空の場合：`~/.claude-chronicle/notes`） |
| `server.host` / `port` | `127.0.0.1` / `8765` | ダッシュボード。このポートが使用中の場合、アプリは空いているポートを使います |
| `server.allowed_hosts` | `[]` | 127.0.0.1 と localhost のほかにダッシュボードが応答する名前。Tailscale の名前など。`chronicle tailnet on` が設定します（[スマートフォンとほかのコンピューター](devices.md#スマートフォン)） |
| `server.allowed_users` | `[]` | それらの名前で Tailscale Serve 経由でアクセスしたとき、通す Tailscale ログイン（空の場合は tailnet の全員）。`chronicle tailnet on` があなたのログインを設定します |
| `inject.session_start` / `max_chars` | `false` / `3000` | 新しいセッションにプロジェクトのナレッジベースの要約を渡す（SessionStart フック） |
| `updates.check_daily` | `false` | ダッシュボードを開いている間、1 日 1 回 pypi.org に最新バージョンを問い合わせる（Status › Updates） |
| `updates.notify` | `false` | バックグラウンド同期が 1 日 1 回 pypi.org に問い合わせ、新しいリリースごとに 1 回デスクトップ通知を表示する（Status › Updates、または `chronicle install --notify-updates`） |

## `[suggestions]`

繰り返し起きる失敗への修正案（[提案と「うまくいかないこと」](suggestions.md)）。

| キー | 既定値 | |
| --- | --- | --- |
| `enabled` | `true` | バックグラウンド同期のたびに提案を更新する（モデルは呼び出しません）。適用するまで何も書き込みません。**Check again** と `chronicle suggest refresh` はどちらの場合も使えます |
| `notify` | `false` | バックグラウンド同期で新しい提案が見つかったら、デスクトップ通知を表示する |

## `[hub]`

複数のコンピューターで 1 つのアーカイブ（[スマートフォンとほかのコンピューター](devices.md#ほかのコンピューター)）。

| キー | 既定値 | |
| --- | --- | --- |
| `url` | `""` | セッションをハブに送るコンピューターで：ハブのアドレス。`chronicle hub join` が設定し、`chronicle hub leave` が消します。設定されている間、このコンピューターは記録・分析をせずにハブへ送ります |
| `path_map` | `{}` | ハブで：ほかのコンピューターのフォルダーのうち、こちらのフォルダーと同じプロジェクトを持つもの。例：`{ "/home/me/code" = "/Users/me/Projects" }`。git リモートのあるプロジェクトは先にリモートで対応付けます |
