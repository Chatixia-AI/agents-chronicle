# チームのハブに参加する

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

チームが Chronicle のハブを運用していて、その管理者から次のようなコマンドが届いたとします。

```bash
chronicle hub join https://chronicle.example.com --code XXXX-XXXX-XXXX --share knowledge
```

このページでは、そのコマンドから始めて、チームのプロジェクトでコーディングエージェントが学んだことを共有し、
チームメイトのナレッジを受け取れるようになるまでを案内します。5 分ほどで終わります。ハブを運用する人は
[Docker でハブを動かす](docker.md)を読んでください。

## 共有されるもの

- **ハブに送られるもの：** 管理者があなたに割り当てたプロジェクトについて、分析済みの各セッションの要約とプロジェクトの
  ナレッジ、およびその詳細（時刻、件数、モデル）。
- **送られないもの：** プロンプト、トランスクリプト、ファイル、コマンド。あなた自身についてのナレッジ（好みなど）。
  ほかのプロジェクトのセッション。ChatGPT や claude.ai から取り込んだチャット。
- **分析はこれまでどおりあなたのコンピューターで行います。** 使うのはあなたの Claude Code、Codex、またはモデル
  プロバイダーです。ハブは何も分析しません。

## 1. Chronicle をインストールする

インストール済みなら飛ばしてください。

```bash
uv tool install --python 3.13 agents-chronicle
chronicle install
```

`chronicle install` の選択肢は[インストール](install.md)で説明しています。

## 2. ハブに参加する

すでにほかのハブに送っている場合は、先にそこから抜けます。

```bash
chronicle hub leave
```

そのうえで、管理者から届いた `chronicle hub join …` コマンドをターミナルで実行します。共有するプロジェクトが
表示されます。

```text
Projects you share with it: Website. Add your folder for each one: …
```

コードは 7 日間、一度だけ使えます。ブラウザーでリンクとして開いても使い切られるので、この手順にはリンクではなく
`chronicle hub join` コマンドを管理者にもらってください。

## 3. プロジェクトのフォルダーを加える

プロジェクトがあなたのコンピューターのどこにあるかをハブに伝えます。

```bash
chronicle hub add-folder ~/code/website --project Website
```

フォルダーはあなたのコンピューターでのプロジェクトのフォルダー、名前は手順 2 で表示されたプロジェクト名です。
これで、そこで分析済みのものが送られます。ハブがすでに知っている git リポジトリのクローンは、この手順がなくても
そのプロジェクトに入りますが、実行しても問題ありません。

ダッシュボードでも同じことができます：**Settings › Devices › Projects on the hub › Join a project** で、
プロジェクトとあなたのフォルダーを選びます。

## 4. 確認する

```bash
chronicle hub status
```

ハブのアドレス、最後に送った時刻、受け取ったチームメイトのナレッジの数が表示されます。ダッシュボードの
**Settings › Devices** にも同じものが表示されます。そこの **Open the hub's dashboard** で、あなたのプロジェクトが
見えるハブのダッシュボードにサインインできます。

## その後

- **分析のたびに、** あなたのコンピューターはプロジェクトの新しい要約とナレッジを送ります。今すぐ送るには
  `chronicle push`、または **Settings › Devices** の **Share now** を使います。
- **送るたびに、** チームメイトがそのプロジェクトで学んだことが返ってきます。エージェントは Chronicle の MCP
  ツールを通じて、チームメイトのものと分かる形でそのナレッジを使えます。セッション開始時のメモを有効にしている場合
  （`chronicle install --inject-context`）、新しいセッションの "From teammates' sessions" にも並びます。
- **あなたのダッシュボード**には、これまでどおりあなた自身のセッションが表示されます。

一つのプロジェクトへの共有をやめるには、**Settings › Devices** でその横の **Leave** を選びます（または
`chronicle hub leave --project <name>`）。そこで共有したものはハブに残ります。間違ったフォルダーを追加したときは、
その横の **Remove** でフォルダーを外すと、あなたのコンピューターがそこから共有したものをハブが削除します。送るのを
すべてやめるには **Leave the hub…** を選びます（または `chronicle hub leave`）。すでに送ったものはハブに残ります。

## うまくいかないとき

- **コードが使えない。** すでに使われたか、7 日を過ぎています。管理者に新しいコードをもらってください。
- **「this hub takes knowledge only」と表示される。** トランスクリプトを送る設定になっています。
  `chronicle config set hub.share knowledge` を実行してから `chronicle push` を実行してください。
- **「This computer is a hub itself」と表示される。** あなたのコンピューターは、ほかのコンピューターが送ってくる
  ハブになっています。用意した人に確認してから、参加の前に `chronicle hub disable` を実行してください。
- **証明書のエラーが出る。** あなたのコンピューターがハブの HTTPS 証明書を信頼していません。管理者に伝えてください。
