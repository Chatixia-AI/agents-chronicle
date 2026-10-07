<p align="center"><img src="packaging/macos/icon.png" width="128" height="128" alt="Chronicle のアプリアイコン：紺色のタイルに重なる琥珀色と空色のセッションページ"></p>

<h1 align="center">Chronicle</h1>

<p align="center"><b>実行したすべてのコーディングエージェントのセッションを、検索できる記憶に。</b><br>
Claude Code、Codex、GitHub Copilot、IBM Bob、Google Antigravity のセッションと claude.ai・ChatGPT のチャットを、自分のマシンの中で保存し、ナレッジに変えます。</p>

<p align="center">
  <a href="https://pypi.org/project/agents-chronicle/"><img src="https://img.shields.io/pypi/v/agents-chronicle?label=PyPI" alt="PyPI のバージョン"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11 以上">
  <img src="https://img.shields.io/badge/macOS-app%20%2B%20CLI-lightgrey?logo=apple" alt="macOS アプリと CLI">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT ライセンス"></a>
  <a href="https://pepy.tech/projects/agents-chronicle"><img src="https://static.pepy.tech/badge/agents-chronicle" alt="累計ダウンロード数"></a>
</p>
<p align="center">
  <a href="https://github.com/Chatixia-AI/agents-chronicle/actions/workflows/ci.yml"><img src="https://github.com/Chatixia-AI/agents-chronicle/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/Chatixia-AI/agents-chronicle/actions/workflows/github-code-scanning/codeql"><img src="https://github.com/Chatixia-AI/agents-chronicle/actions/workflows/github-code-scanning/codeql/badge.svg?branch=main" alt="CodeQL"></a>
  <a href="https://chronicle.chatixia.net/docs/"><img src="https://github.com/Chatixia-AI/agents-chronicle/actions/workflows/docs.yml/badge.svg?branch=main" alt="Docs"></a>
  <a href="https://pre-commit.com/"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center"><a href="#クイックスタート">クイックスタート</a> · <a href="docs/ja/README.md">ドキュメント</a> · <a href="CHANGELOG.md">変更履歴</a> · <a href="ROADMAP.ja.md">ロードマップ</a> · <a href="README.md">English</a></p>

コーディングエージェントは一日中問題を解決しますが、その教訓はすぐに消えてしまいます。Claude Code はトランスクリプトを
30 日で削除し、あるセッションで見つけた修正が次のセッションに引き継がれることもありません。Chronicle はすべてのセッションを
保存し、Claude Code または Codex を使って学んだことを取り出し、ダッシュボードであなたに、MCP サーバー経由でエージェントに返します。

![Chronicle のセッションページ：1 行にまとまったツール呼び出しを含む会話、そこから抽出したナレッジ、プロンプトのアウトライン](docs/images/session.png)

## 何が得られるか

Chronicle は終わったセッションを読み、残す価値のあることを書き留めます。以下は[デモデータ](docs/ja/development.md#デモデータ)から
そのまま取り出した実例です（デモデータは英語です）。

> **Gotcha** · billing-api<br>
> **Stripe webhook signatures need the raw request body**<br>
> `Webhook.construct_event` verifies the signature over the exact bytes Stripe sent. Parsing to JSON first, or
> posting `json=` in tests, fails with `SignatureVerificationError`. Read `await request.body()` and pass that.<br>
> <sub>セッション「Stop double charges when Stripe retries invoice.paid」から自動で抽出。</sub>

- **すべてのセッションを残す。** 元のトランスクリプトを保管するので、エージェントが片付けても何も失われません。
- **ナレッジを自動で抽出。** 修正、落とし穴、決定、コマンド、プロジェクトの事実、好みを、プロジェクトごとのナレッジベースと、
  全プロジェクト共通のプレイブックにまとめます。
- **エージェントから質問できる。** [MCP サーバー](docs/ja/mcp.md)経由で、エージェントが過去のセッションを検索できます。例：
  「このエラー、前にも出た？」「なぜ冪等性を Postgres でやることにしたんだっけ？」Claude Desktop、Cursor、Windsurf、
  Gemini CLI からも接続できます。
- **すべてを眺めるダッシュボード。** トランスクリプト全体を含むセッション、統計、自分の用語をマインドマップにした用語集、
  ひと目でわかる週次の振り返り。⌘K でどこへでも移動できます。
- **システムのマップ。** すべてのプロジェクトをシステムとして、そのパーツ（UI、API、データベース、CI、デプロイ先）と
  プロジェクト同士のつながりを、マニフェストとセッションが行ったことから、根拠つきで描きます。
- **エージェントが作ったものを一か所に。** すべてのセッションのドキュメント、ページ、図、スライド、プルリクエスト、コミットを、
  作ったセッションへのリンク付きで、ファイルが変わった・なくなったときは印を付けて並べます。
- **スマートフォンとほかのコンピューターでも。** Tailscale 経由でスマートフォンからダッシュボードを開き、すべてのコンピューターの
  セッションを 1 つのアーカイブにまとめて、分析は 1 回だけ（[スマートフォンとほかのコンピューター](docs/ja/devices.md)）。
- **VS Code で、コードのすぐ横に。** [拡張機能](docs/ja/vscode.md)が、開いているファイルの背後にあるセッションと、
  ワークスペースでエージェントが作業したすべてのファイルを表示します。
- **ただのファイルとしても。** Obsidian 互換の Markdown 保管庫と `chronicle` CLI。

## クイックスタート

macOS 13 以降と、ログイン済みの [Claude Code](https://claude.com/claude-code) または [Codex](https://github.com/openai/codex)
（分析を担当）が必要です。

1. **インストール。**

   ```bash
   uv tool install --python 3.13 agents-chronicle   # または: pipx install agents-chronicle
   chronicle install
   ```

   `chronicle install` は Mac にあるコーディングエージェントを見つけ、どれを記録するか尋ね、過去のセッションを取り込み、
   ログイン時から Chronicle を動かすかを尋ねます。アプリがよければ[最新リリース](https://github.com/Chatixia-AI/agents-chronicle/releases/latest)
   （Apple シリコン）からダウンロードして **Connect** を選びます。

2. **いつも通りエージェントを使う。** 各セッションは終了時に記録され、バックグラウンドで分析されます。

3. **眺める。** ダッシュボード <http://127.0.0.1:11524/>（または `chronicle ui --open`）を開いて **⌘K** を押すか、
   エージェントに「先週何を学んだ？」と聞きます。

エージェントはあとから **Settings › Sources**、`chronicle connect <agent>`、または `chronicle install` の再実行で追加できます。
各ステップが何を設定するか、削除の仕方は[インストール](docs/ja/install.md)にあります。

## 対応エージェント

| エージェント | 記録元 | 取り込み | エージェントからの検索（MCP） |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/projects` のトランスクリプト | セッション終了ごと、および 15 分ごと | ✅ |
| Codex | `~/.codex/sessions` のロールアウト | 15 分ごと（アイドルになってから） | ✅ |
| Codex Cloud | chatgpt.com/codex のタスク（`codex` CLI 経由。タイトル、リポジトリ、差分） | 15 分ごと | Codex 経由 |
| GitHub Copilot | Copilot CLI とエージェントのセッション、VS Code の Copilot Chat ログ | 15 分ごと | ✅ VS Code と Copilot CLI |
| IBM Bob | `~/.bob/db/bob.db`（読み取り専用） | 15 分ごと | ✅ |
| Google Antigravity | `~/.gemini/antigravity` の会話ログ（読み取り専用） | 15 分ごと | ✅ |
| claude.ai、ChatGPT | データエクスポート：`chronicle import <zip>` | 取り込んだとき | – |

すべて同じダッシュボード、ナレッジ、用語集、MCP ツールを共有します。分析は Claude Code と Codex のうち、選んだほうで行います。
詳しくは[ソース](docs/ja/sources.md)を参照してください。

## もう少し詳しく

| | | |
| --- | --- | --- |
| ![ホーム：30 日間の稼働時間、セッション、トークン、推定コスト、日次グラフと結果](docs/images/home.png) | ![マップ：用語集のマインドマップ。用語を開くと定義、使われ方、出どころが出る](docs/images/map.png) | ![⌘K パレット：セッション、ナレッジ、用語をまとめて検索](docs/images/palette.png) |
| **ホーム。** 稼働時間、セッション、トークン、推定コストを日ごとに。 | **マップ。** 用語集をマインドマップに。各用語から、その背後のナレッジとセッションへ。 | **⌘K。** セッション、ナレッジ、プロジェクト、用語、コマンドをひとつの検索で。 |

スクリーンショットは架空の[デモデータ](docs/ja/development.md#デモデータ)です。

## 仕組み

![Chronicle の仕組み：ソース、アーカイブ、解析、SQLite、claude -p または codex exec による分析、ナレッジ、そしてダッシュボード・保管庫・CLI・MCP サーバー](docs/diagrams/architecture.excalidraw.svg)

1. フック（または 15 分ごとの同期）が終わったセッションを Chronicle に渡し、Chronicle は元のトランスクリプトを保管して
   解析します：プロンプト、応答、ツール呼び出し、ファイル、トークン、コスト。
2. セッションがアイドルになると、秘密情報を伏せた要約版のダイジェストが、選んだほうの Claude Code（`claude -p`）または
   Codex（`codex exec`）に送られ、要約とナレッジ項目が返ってきます。この呼び出しはサンドボックス内で動き、ツール、フック、
   MCP サーバーは使いません。
3. 新しいナレッジはプロジェクトのナレッジベースにまとめられ、用語集が更新され、終わった週ごとに振り返りが書かれます。
4. すべてがあなた（ダッシュボード、アプリ、保管庫、CLI）とエージェント（MCP）に提供されます。

**マシンの外に出るもの：** その伏せ字済みのダイジェストだけで、あなた自身の Claude Code または Codex のログインを通じて
Anthropic または OpenAI に送られます。テレメトリはなく、ほかの誰にも何も送りません。何がどこに保存されるかは[データとプライバシー](docs/ja/privacy.md)に
あります。

**費用：** 分析は、そのエージェントのほかの利用と同じように Claude または ChatGPT のプランから使われます。Claude の場合、
API 換算では Sonnet で 1 セッションあたり平均約 $0.38 です。`chronicle analyze --pending --dry-run` で、使う前にたまった分の規模を確認できます。
詳しくは[分析の仕組み](docs/ja/analysis.md)を参照してください。

## よくある質問

**エージェントが遅くならない？** なりません。セッション終了フックは切り離したプロセスに処理を渡し、数ミリ秒で戻ります。
分析はあとでバックグラウンドで行います。

**Claude Code は必須？** いいえ。分析は Claude Code、Codex、IBM Bob のほか、あなた自身のキーでモデルプロバイダーの API でも行えます：
Anthropic、Amazon Bedrock、OpenAI、Azure OpenAI、OpenRouter、OpenAI 互換の任意のサーバー、またはあなたのコンピューター上の
Ollama。**Status › Analysis** または `chronicle config set analysis.backend <name>` で選びます
（[モデルプロバイダー](docs/ja/analysis.md#モデルプロバイダー)）。記録と閲覧はどれでも使えます。何も設定していない場合、
セッションは保管され、分析待ちの列で待ちます。

**Windows や Linux は？** デスクトップアプリは macOS 専用です。Linux では `chronicle install` が同期とダッシュボードを systemd の
ユーザーユニットとして動かすので、Linux マシンをほかのコンピューターの[ハブ](docs/ja/devices.md#linux-のハブ)にできます。
チームのハブは [Docker](docs/ja/docker.md) でも動かせます。
Windows にはまだ対応していません。

**特定のプロジェクトやセッションを除外できる？** [設定](docs/ja/configuration.md)の `sources.exclude_projects` に
プロジェクトを追加するか、`chronicle forget <id>` でセッションを完全に削除します。

**削除するには？** `chronicle uninstall` でフック、バックグラウンドのエージェント、MCP の登録を削除します（データは残ります）。
データも消すには `--purge` を付けます。

うまく動かないときは[トラブルシューティング](docs/ja/troubleshooting.md)を参照してください。

## ドキュメント

[インストール](docs/ja/install.md) · [ソース](docs/ja/sources.md) · [ダッシュボード・用語集・マップ](docs/ja/dashboard.md) ·
[コマンドライン](docs/ja/cli.md) · [MCP サーバー](docs/ja/mcp.md) · [VS Code 拡張機能](docs/ja/vscode.md) ·
[スマートフォンとほかのコンピューター](docs/ja/devices.md) · [Docker でハブを動かす](docs/ja/docker.md) ·
[チームのハブに参加する](docs/ja/join-a-hub.md) ·
[記録内容と分析の仕組み](docs/ja/analysis.md) · [設定](docs/ja/configuration.md) ·
[データとプライバシー](docs/ja/privacy.md) · [トラブルシューティング](docs/ja/troubleshooting.md) · [開発](docs/ja/development.md)

## コントリビュート

Issue やプルリクエストを歓迎します。テストの実行方法や、自分のセッションの代わりにデモデータでダッシュボードを開発する方法は
[CONTRIBUTING.md](CONTRIBUTING.md) にあります。

## ライセンス

[MIT](LICENSE)。ただし [`ee/`](ee/) ディレクトリは例外です。企業がチーム全体で Chronicle を運用するための機能
（シングルサインオン、ポリシー、監査ログのエクスポート）は [Chronicle Enterprise License](ee/LICENSE) で提供し、本番利用には
サブスクリプションが必要です。PyPI の `agents-chronicle` パッケージは MIT のみです。
