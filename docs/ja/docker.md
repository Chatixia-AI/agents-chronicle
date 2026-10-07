# Docker でハブを動かす

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

このガイドでは、Docker が動くサーバーにチームの[ハブ](devices.md#ほかのコンピューター)を用意します。空のサーバーから、
チームメイトがプロジェクトで学んだことを共有できるようになるまでです。ハブを運用する人向けです。チームメイトは
代わりに[チームのハブに参加する](join-a-hub.md)を読んでください。

`docker/compose.yaml` は次の 3 つのコンテナーを起動します。

- **ハブ**：イメージ `ghcr.io/chatixia-ai/chronicle-hub`
- **Caddy**：ハブの前に立ち、HTTPS の証明書を取得・更新します
- **Postgres**：[チームストア](devices.md#チームメイトのナレッジとpostgres-のチームストア)。各コンピューターが学んだことを
  まとめ、チームメイトのナレッジを送り返します

ハブが受け取るのは**ナレッジだけ**です。各コンピューターは自分のセッションを自分の Claude Code、Codex、またはモデル
プロバイダーで記録・分析し、各セッションの要約とプロジェクトのナレッジだけをハブに送ります。トランスクリプト、
プロンプト、ファイルパスはコンピューターに残ります。ハブは何も分析しないので、モデルも API キーも要りません。

## 必要なもの

- **Docker が動く Linux サーバー**（SSH で接続できるもの）。CPU 2 つとメモリー 4 GB で十分です。
- **ポート 80 と 443**：ハブを使うコンピューターから届くように開けておきます。Caddy が Let's Encrypt から証明書を
  取得するのにも使います。
- **ハブの名前**：`chronicle.example.com` のように、DNS がサーバーを指す名前です。まだない場合は、サーバーの IP
  アドレスをハイフンでつなぎ `.sslip.io` を付けた名前で試せます。`172-207-25-249.sslip.io` は `172.207.25.249` を
  指す無料の名前です。社内ネットワークからしか届かない名前の場合は[自分の証明書を使う](#自分の証明書を使う)を
  参照してください。

サーバーに Docker を入れるには：

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
```

### Azure の場合

- **仮想マシンを使います**：Ubuntu、サイズは B2s 程度。Azure Container Apps や App Service は使えません。ファイルを
  ネットワーク共有の Azure Files に置くため、ハブの SQLite データベース（WAL モード）が安定して動かないからです。
- **自分の鍵を使います。** **管理者アカウント**で **既存の公開キーを使用** を選び、ハブ用に作った鍵の公開鍵を
  貼り付けます。

    ```bash
    ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_chronicle_hub -C chronicle-hub
    pbcopy < ~/.ssh/id_ed25519_chronicle_hub.pub
    ```

    代わりに **新しいキーの組の生成** を選ぶと、VM の作成の最後に **秘密キーのダウンロード** ダイアログが
    出ます。エラーではありません。そこで鍵をダウンロードしたときに初めて VM が作られます。
- **ポートを開けます**：VM の **ネットワーク** › **受信ポートの規則を追加** で、80 と 443 をそれぞれ追加します。
- **名前を付けます**：VM のパブリック IP アドレス › **構成** › **DNS 名ラベル** で
  `<ラベル>.<リージョン>.cloudapp.azure.com` になります。上の sslip.io の名前でもかまいません。

接続は `ssh -i ~/.ssh/id_ed25519_chronicle_hub azureuser@<VM の IP アドレス>` です。

## ハブを用意する

手順 1〜3 はサーバーで実行します。

### 1. ファイルをダウンロードする

```bash
mkdir ~/chronicle-hub && cd ~/chronicle-hub
base=https://raw.githubusercontent.com/Chatixia-AI/agents-chronicle/main/docker
curl -fsSL "$base/compose.yaml" -o compose.yaml
curl -fsSL "$base/Caddyfile" -o Caddyfile
curl -fsSL "$base/.env.example" -o .env
```

### 2. 設定を埋める

チームストアのデータベース用のパスワードを作ってコピーし、`.env` を開きます。

```bash
openssl rand -hex 24
nano .env
```

次の 4 行を設定します。nano では Ctrl+O のあと Enter で保存、Ctrl+X で終了します。

```bash
CHRONICLE_DOMAIN=chronicle.example.com   # ハブの名前
CHRONICLE_ADMIN_EMAIL=you@example.com    # 最初の管理者（あなた）
CHRONICLE_ADMIN_NAME=You
POSTGRES_PASSWORD=...                    # コピーしたパスワード
```

### 3. 起動する

```bash
docker compose up -d
docker compose logs hub
```

ログに、ハブの最初の管理者としてのあなたの招待が出ます。

```text
Added You (you@example.com) as this hub's admin. The invite works once, for 7 days:

  In a browser, to open the hub's dashboard:  https://chronicle.example.com/signin?code=ABCD-EFGH-JKLM
  Or on their computer, to join it:           chronicle hub join https://chronicle.example.com --code ABCD-EFGH-JKLM --share knowledge
```

これが表示されるのは**ハブの最初の起動のときだけ**です。再起動しても利用者はそのままで、招待は表示されません。
見逃したときや期限が切れたときは、新しく作ります。

```bash
docker compose exec hub chronicle hub invite you@example.com
```

ハブに管理者ができるまで、コンテナーは何も提供しません。利用者のいないハブは、届いた人を誰でも管理者として通して
しまうため、`CHRONICLE_ADMIN_EMAIL` なしで起動するとエラーで止まり、何も提供しません。

### 4. サインインする

招待の**リンク**をブラウザーで開きます。これでハブの管理者です。サイドバーの **Team** に、利用者、プロジェクト、
コンピューター、チームストアがあります。

## プロジェクトを追加する

ハブのプロジェクトは、ハブのコンピューター上のフォルダーで、名前はフォルダー名になります。コンテナーでは、そのフォルダーは
作るまで存在しません。ダッシュボードの **Team › Shared projects** では作れません。プロジェクトを用意できるのは
ハブのコンピューターにいる人だけで、コンテナーのダッシュボードにはそういう形で届くことがないためです。そこでサーバーの
`~/chronicle-hub` で：

```bash
docker compose exec hub mkdir -p /data/projects/Website
docker compose exec hub chronicle hub project add /data/projects/Website
docker compose exec hub chronicle hub project list
```

フォルダーにはプロジェクトの名前を付けます（ここでは `Website`）。あとは各コンピューターがそれぞれのフォルダーを
プロジェクトに加えます（次の節）。あるコンピューターが git リポジトリのセッションを送ると、同じリポジトリのほかの
クローンは自動でそのプロジェクトに入ります。

## 自分のコンピューターをつなぐ

自分のコンピューターも、チームメイトと同じように参加します。専用の招待と、その招待が表示する `chronicle hub join`
コマンドを使います。まず、何を共有するかを決めます。

- **そのプロジェクトだけ。** そのプロジェクトだけが見える人としてコンピューターを招待します。ブラウザーは管理者の
  サインインのままです。

    ```bash
    docker compose exec hub chronicle hub invite "Your Mac" --project Website
    ```

- **分析したすべて。** `docker compose exec hub chronicle hub invite you@example.com` で自分の新しいコードを作り、
  それで参加します。分析したコーディングエージェントのセッションすべての要約とプロジェクトのナレッジが送られ、
  すべてのプロジェクトがハブに現れます。

どちらの場合も、ChatGPT や claude.ai から取り込んだチャットはコンピューターから出ません。

招待はそれぞれ 2 つのものを表示し、そのコードは**どちらか一方に一度だけ**使えます。

- **`chronicle hub join …` コマンド**はコンピューターをつなぎます。ターミナルで実行します。
- **`https://…/signin?code=…` リンク**はダッシュボードを開きます。ブラウザーで開きます。

リンクを開くとコードは使い切られ、コンピューターには新しいコードが必要になります。

自分のコンピューターで：

```bash
chronicle hub disable    # このコンピューター自体がハブの場合だけ
chronicle hub leave      # ほかのハブに参加している場合だけ
chronicle hub join https://chronicle.example.com --code XXXX-XXXX-XXXX --share knowledge --no-push
chronicle hub add-folder ~/Projects/Website --project Website
```

`add-folder` はすぐに送ります。`3 sessions shared … 300 excluded` のような結果は、そのプロジェクトの分析済みの
セッション 3 件がハブに送られ、ほかの 300 件はコンピューターに残ったことを意味します。ダッシュボードの **Projects** を
再読み込みすると表示されます。

## チームを招待する

サーバーで、1 人ずつ招待します。

```bash
docker compose exec hub chronicle hub invite "Yuma" --email yuma@example.com --project Website
```

リンクではなく `chronicle hub join …` の行を、[チームのハブに参加する](join-a-hub.md)と一緒に送ってください。
残りの手順はそのページが案内します。ダッシュボードも使えるようにするには、
`docker compose exec hub chronicle hub invite yuma@example.com` で 2 つ目のコードを作り、その**リンク**を送ります。

ダッシュボードの **Team › People** でも、ロールと見えるプロジェクトを選んで招待できます。

## よく使うコマンド

サーバーの `~/chronicle-hub` で：

| すること | コマンド |
|---|---|
| 利用者と、それぞれに見えるものを一覧する | `docker compose exec hub chronicle hub people` |
| 送ってくるコンピューターと、最後に送った時刻を見る | `docker compose exec hub chronicle hub status` |
| プロジェクトを一覧する | `docker compose exec hub chronicle hub project list` |
| すでにいる人の新しいコードを作る | `docker compose exec hub chronicle hub invite <メールアドレスか ID>` |
| 見えるプロジェクトを変える | `docker compose exec hub chronicle hub access <メールアドレスか ID> --project <名前>` |
| 利用者を外す | `docker compose exec hub chronicle hub remove <メールアドレスか ID>` |
| ハブのログを読む | `docker compose logs hub` |

新しいコードを作るときは、メールアドレスか、`hub people` が表示する ID を使ってください。名前をもう一度入力すると、
2 人目の利用者が加わります。

## ハブが受け取るもの

コンテナーは最初の起動時に次の 2 つを設定します。どちらも管理者があとで変更できます。

| 設定 | 値 | 意味 |
|---|---|---|
| `[hub] accept` | `"knowledge"` | トランスクリプトを送ってくるコンピューターを受け付けません。 |
| `[hub] shared_token` | `false` | コンピューターはハブの共有トークンではなく、それぞれの招待で参加します。 |

ハブにトランスクリプトを受け取らせて自分で分析させるには、モデルプロバイダーの API が必要です。イメージには
Claude Code も Codex も入っていないので、ここでは使えません。

```bash
docker compose exec hub chronicle config set hub.accept everything
docker compose exec hub chronicle config set analysis.backend anthropic
docker compose exec hub chronicle config set-key anthropic   # キーを尋ねられます
docker compose restart hub
```

ほかのプロバイダーは[モデルプロバイダー](analysis.md#モデルプロバイダー)を参照してください。

## 設定

コンテナーは起動のたびに、次の変数から `config.toml` を設定します。値のある変数は `config.toml` より優先され、
未設定または空の変数は `config.toml` をそのままにします。それ以外の設定は `config.toml` に残ります。
`docker compose exec hub chronicle config set ...` で変更し、ハブを再起動してください。

| 変数 | 既定値 | |
|---|---|---|
| `CHRONICLE_HUB_URL` | （必須） | コンピューターとブラウザーがハブに届くアドレス。`[hub] address` になり、そのホスト名が `[server] allowed_hosts` に加わります。`compose.yaml` は `CHRONICLE_DOMAIN` から設定します。 |
| `CHRONICLE_ADMIN_EMAIL` | （最初は必須） | 最初の管理者。ハブに利用者がいないときに追加されます。 |
| `CHRONICLE_ADMIN_NAME` | メールアドレスの @ より前 | その人の名前。 |
| `CHRONICLE_HUB_NAME` | `Chronicle hub` | ダッシュボードに表示される名前（`[hub] name`）。 |
| `CHRONICLE_HOST` | `0.0.0.0` | ダッシュボードが待ち受けるアドレス。`compose.yaml` は `127.0.0.1` にします。ハブは Caddy のネットワークを共有するので、届くのは Caddy だけです。 |
| `CHRONICLE_PORT` | `11524` | ダッシュボードのポート。 |
| `CHRONICLE_ALLOWED_HOSTS` | | ダッシュボードが応答するほかの名前（カンマ区切り）。 |
| `CHRONICLE_TRUSTED_PROXIES` | `127.0.0.1, ::1` | ハブが `X-Forwarded-Proto` を信じるプロキシのアドレス（カンマ区切り）。自分のプロキシからコンテナーに転送するときに設定します（[下記](#自分のプロキシを使う)）。 |
| `CHRONICLE_TEAM_STORE` | | `postgres` にすると、チームストアを Postgres に置き、`PGHOST`、`PGDATABASE`、`PGUSER`、`PGPASSWORD`、`PGSSLMODE` で接続します。`compose.yaml` はすべて設定済みです。 |
| `CHRONICLE_WORK_MINUTES` | `15` | ハブが送られてきたものを読み込み、バックグラウンドの処理を実行する間隔（分）。`0` で止めます。 |

ハブが保持するものはすべて `hub-data` ボリューム（コンテナー内の `/data`）にあります。チームストアのデータは
`postgres-data` ボリュームにあります。

## 自分の証明書を使う

Caddy は Let's Encrypt から証明書を取得します。そのためには Let's Encrypt がサーバーのポート 80 か 443 に届く必要が
あります。社内ネットワークからしか届かない名前の場合は、会社の証明書を Caddy に渡します。`compose.yaml` の `caddy`
の `volumes` に `- ./certs:/certs:ro` を加えてマウントし、`Caddyfile` に `tls` の行を加えます。

```text
{$CHRONICLE_DOMAIN} {
	tls /certs/chronicle.crt /certs/chronicle.key
	reverse_proxy 127.0.0.1:11524
}
```

`tls internal` にすると、Caddy が自分で証明書を作ります。その場合、ハブを使うすべてのコンピューターとブラウザーが
Caddy のルート証明書を信頼する必要があります。

## 自分のプロキシを使う

`compose.yaml` を使わずにイメージだけを動かし、自分の HTTPS プロキシ（nginx、ロードバランサー）を前に置くこともできます。
[Tailscale を使わずにハブにつなぐ](devices.md#tailscale-を使わずにハブにつなぐ)と同じ構成です。

```bash
docker run -d --name chronicle-hub --restart unless-stopped -p 11524:11524 -v chronicle-hub:/data \
  -e CHRONICLE_HUB_URL=https://chronicle.example.internal -e CHRONICLE_ADMIN_EMAIL=you@example.com \
  -e CHRONICLE_TRUSTED_PROXIES=10.0.4.12 ghcr.io/chatixia-ai/chronicle-hub
```

`CHRONICLE_TRUSTED_PROXIES` には、コンテナーから見たプロキシのアドレスを設定します。こうするとハブはプロキシの
`X-Forwarded-Proto` を信じ、サインインの Cookie に `Secure` を付けます。同じサーバー上のプロキシが公開ポートに
つなぐ場合、たいていは Docker のブリッジのゲートウェイ `172.17.0.1` です。ポート 11524 にはプロキシだけが
届くようにしてください。チームストアがないと、共有したコンピューターにチームメイトのナレッジは返りません。
Postgres を加えるには `CHRONICLE_TEAM_STORE=postgres` と `PG*` 変数を設定します。

## 更新する

```bash
docker compose pull
docker compose up -d
```

バージョンを固定するには、`.env` の `CHRONICLE_VERSION` を設定します（例：`0.13.0`）。ダッシュボードからはコンテナーを
アップデートできません。**Status** には、代わりに新しいイメージを取得するよう表示されます。

## バックアップする

ハブの動作中にデータベースをコピーし、チームストアをダンプします。

```bash
docker compose exec hub python -c "import sqlite3; sqlite3.connect('/data/chronicle.db').backup(sqlite3.connect('/data/backup.db'))"
docker compose cp hub:/data/backup.db ./chronicle-backup.db
docker compose exec -T postgres pg_dump -U chronicle chronicle > team-store.sql
```

ハブの動作中に `chronicle.db` そのものをコピーしないでください。コピーが壊れることがあります。

## トラブルシューティング

**ログに招待が出ない。** 最初の管理者の招待は、ハブの最初の起動のときだけ表示されます。
`docker compose exec hub chronicle hub invite you@example.com` で新しく作ってください。

**起動の直後にページがエラーになる。** Caddy はハブより先に起動し、ハブが起動するまでの数秒間はエラーを返します。
ページを再読み込みしてください。

**コンピューター用のコードをブラウザーで開いてしまった、または期限が切れた。** その人のメールアドレスか ID で新しい
コードを作ります（例：`docker compose exec hub chronicle hub invite 3`）。

**`chronicle hub join` が、このコンピューターはハブだと言う。** 先にそのコンピューターで `chronicle hub disable` を
実行します。保持しているものはそのまま残りますが、ほかのコンピューターはそこへ送れなくなります。

**自分のダッシュボード `http://127.0.0.1:11524/` が応答しなくなった。** VS Code の Remote-SSH でサーバーにつなぎ、
ハブのログを読んだあとに起こります。0.13.0 のイメージは `Chronicle dashboard: http://127.0.0.1:11524/` と表示し、
VS Code がそのポートを自分のコンピューターへ転送して、自分のダッシュボードの前に立ってしまいます。サーバーにつないだ
VS Code のウィンドウ（隅に **SSH: …** と表示されるもの）で **Ports** を開き、11524 を右クリックして **Stop
Forwarding Port** を選びます。VS Code の設定に `"remote.portsAttributes": { "11524": { "onAutoForward": "ignore" } }` を
加えると、再発しません。以降のイメージは代わりに `Chronicle hub is up: <ハブのアドレス>` と表示します。

**HTTPS がつながらない。** 名前がサーバーの IP アドレスを指しているか、ポート 80 と 443 が開いているか、
`docker compose logs caddy` の内容を確認してください。社内ネットワークからしか届かないサーバーには Let's Encrypt が
届きません。[自分の証明書](#自分の証明書を使う)を使ってください。sslip.io の名前をブロックする社内ネットワークも
あります。その場合は自分の名前を使ってください。
