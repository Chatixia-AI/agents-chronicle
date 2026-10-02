# スマートフォンとほかのコンピューター

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

Chronicle は 1 台のコンピューターにアーカイブを置きます。そのダッシュボードをスマートフォンで開いたり、ほかのコンピューターの
セッションも同じアーカイブにまとめたりできます。どちらも [Tailscale](https://tailscale.com)（自分のデバイスどうしの
プライベートなネットワーク）を通るので、インターネットには何も公開されません。

1 台が**ハブ**になります。セッションを記録し、分析し、ダッシュボードを提供するのはハブだけです。デスクトップの Mac、Mac mini、
Linux マシンなど、いちばん長く電源が入っているものを選んでください。ほかのコンピューターはハブにセッションを**送り**、
スマートフォンはハブのダッシュボードを開きます。書き込むのがハブだけなので、各セッションの分析（とその費用）は 1 回だけで、
マージするものもありません。

## スマートフォン

1. ハブとスマートフォンに Tailscale をインストールし、両方を同じアカウントでサインインします。
2. ハブで次を実行します。

   ```bash
   chronicle tailnet on
   ```

   初回は、tailnet で Serve と HTTPS 証明書を有効にするためのリンクを Tailscale が表示することがあります。開いて有効にし、
   コマンドが止まっていればもう一度実行してください。
3. スマートフォンで（Tailscale アプリをオンにして）、表示されたアドレス `https://<コンピューター>.<tailnet>.ts.net/` を開きます。
   iPhone では **共有 › ホーム画面に追加** でアイコンができ、アプリのように開けます。Android では **⋮ › ホーム画面に追加** です。

スマートフォンではセクションが画面下のタブバーに並び、ページが画面の幅いっぱいに広がります。セッションはカードで表示されます。
検索、ナレッジ、振り返り、ピン留めや非表示など、コンピューターと同じことができます。

仕組み：Tailscale Serve がこの HTTPS アドレスをダッシュボードに転送します。ダッシュボード自体は引き続き 127.0.0.1 だけで
待ち受けます。ダッシュボードはこの名前（`[server] allowed_hosts`）に応答し、Serve が伝えるあなたの Tailscale ログイン
（`[server] allowed_users`）だけを通します。`chronicle tailnet on --anyone` で tailnet の全員を通し、`chronicle tailnet status`
で設定を確認し、`chronicle tailnet off` で tailnet から外します。ハブではダッシュボードが動いている必要があります。
`chronicle install` がバックグラウンドで動かし続けます。

## ほかのコンピューター

ハブで `chronicle tailnet on` のあと、次を実行します。

```bash
chronicle hub enable
```

ハブのアドレスとトークンの入ったコマンドが表示されます。ほかのコンピューターに [Chronicle をインストール](install.md)し、
そこでそのコマンドを実行します。

```bash
chronicle hub join https://pc.tail1234.ts.net --token …
```

そのコンピューターにある Claude Code と Codex のセッションがすべてハブに送られ、ハブが記録して分析します。以後は次のとおりです。

- **新しいセッションはハブへ送られます。** そのコンピューターで `chronicle install` がフックとバックグラウンド同期を設定していれば、
  セッションが終わるたび（SessionEnd フック）と 15 分ごと（バックグラウンド同期）に送ります。`chronicle push` ですぐに送れます。
- **ハブは各セッションをどこで実行したか知っています。** セッションのページにどのコンピューターのものかが表示され、
  **Settings › Devices** にコンピューターと、それぞれのセッション数、最後に送ってきた時刻が並びます（ターミナルでは
  `chronicle hub status`）。
- **分析はハブだけで行います。** そのコンピューターが自分の Chronicle ですでに分析していたセッションは、参加するときにその結果を
  ハブに引き渡すので、ハブがもう一度費用をかけて分析することはありません。
- **そのコンピューター自身のダッシュボードと MCP ツールは更新されなくなります。** それまでの内容は残ります。代わりにハブの
  ダッシュボードを開いてください（**Settings › Devices** にリンクがあります）。

### 同じプロジェクト、別のフォルダー

同じリポジトリでも、コンピューターによってフォルダーが違うことはよくあります。ハブは各セッションを自分の側の同じプロジェクトに
まとめます。

1. **git のリモートで。** ほかのコンピューターが各プロジェクトフォルダーの git リモートを知らせます（Codex のセッションは自分でも
   記録しています）。同じリモートを持つハブ側のフォルダーにまとめます。
2. **`[hub] path_map` で。** リモートのないプロジェクト向けに、ハブの[設定](configuration.md#hub)で指定します。

   ```toml
   [hub]
   path_map = { "/home/me/code" = "/Users/me/Projects" }
   ```

どちらにも当てはまらなければ、セッションは実行されたフォルダーのままです。セッションのページでコンピューター名にポインターを
合わせると、元のフォルダーが表示されます。

### 送られるもの

- `claude_dirs` の各フォルダーから `projects/`（トランスクリプト、サブエージェントのスレッド、メモリーのメモ）と `history.jsonl`。
  `codex_dirs` の各フォルダーから `sessions/`、`memories/`、Codex のセッション一覧。
- `sources.exclude_projects` にあるプロジェクトは送りません。
- GitHub Copilot、IBM Bob、Google Antigravity、Codex Cloud、チャットのエクスポートは送りません。これらはハブで接続または取り込みます。
- ファイルは tailnet 内の HTTPS で圧縮して送られ、到着時に SHA-256 で照合されます。送るのはハブにないファイルか、ハブのものが
  古いファイルだけです。各コンピューターはハブのトークンで認証します。トークンは `~/.claude-chronicle/hub-token` にあり、
  あなたのユーザーだけが読めます。`chronicle hub enable --rotate` で作り直すと、ほかのコンピューターは参加し直す必要があります。
- ハブは受け取ったものを `~/.claude-chronicle/machines/<コンピューター>/` に置き、自分のものと同じようにアーカイブします。

### やめるとき

コンピューターで `chronicle hub leave` を実行すると、そのコンピューターは再び自分でセッションを記録・分析します。ハブは受け取った
ものを残します。ハブで `chronicle hub disable` を実行すると、セッションを受け付けなくなります。

## Linux のハブ

Linux では `chronicle install` が launchd エージェントの代わりに systemd のユーザーユニットを設定します。
`chronicle-sync.timer`（15 分ごとの同期）と `chronicle-ui.service`（ダッシュボード）です。無人で動かすハブには、
次の 2 つを一度だけ実行しておくと便利です。

```bash
loginctl enable-linger $USER             # 誰もログインしていなくても動かし続ける
sudo tailscale set --operator=$USER      # `chronicle tailnet on` が Tailscale Serve を設定できるようにする
```

デスクトップアプリは macOS 専用です。コマンドラインとダッシュボードは同じように動きます。

## ハブを使わない方法：Syncthing

ハブを動かしたくない場合は、[Syncthing](https://syncthing.net)（または rsync）でほかのコンピューターのセッションをメインの
コンピューターにコピーできます。`~/.claude/projects` を `~/sessions/laptop/claude/projects` のようなフォルダーに、
`~/.codex/sessions` を `~/sessions/laptop/codex/sessions` に同期し、`~/sessions/laptop/claude` を `claude_dirs` に、
`~/sessions/laptop/codex` を `codex_dirs` に加えます。Chronicle はこれを自分のセッションとして記録します。コンピューター名、
プロジェクトの対応付け、それまでの分析の引き継ぎはありません。

`~/.claude-chronicle` そのものをコンピューター間で同期しないでください。使用中にコピーされた SQLite データベースは壊れることが
あります。

## まだできないこと

- **スマートフォンの Claude アプリ。** Claude のカスタムコネクターはスマートフォンからではなく Anthropic のクラウドから MCP サーバーに
  接続するので、ハブの tailnet 内のアドレスには届きません。スマートフォンから Claude Code の Remote Control でハブのセッションを
  操作すれば、Chronicle のツールを使えます。
- **ほかのコンピューターでオフラインで読めるコピー。**
- **Windows。**
