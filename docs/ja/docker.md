# Docker でハブを動かす

[← Chronicle](../../README.ja.md) · [ドキュメント一覧](README.md)

チームの[ハブ](devices.md#ほかのコンピューター)は、Docker が動く任意のサーバーで動かせます。`docker/compose.yaml` は
次の 3 つのコンテナーを起動します。

- **ハブ**：イメージ `ghcr.io/chatixia-ai/chronicle-hub`
- **Caddy**：ハブの前に立ち、HTTPS の証明書を取得・更新します
- **Postgres**：[チームストア](devices.md#チームメイトのナレッジとpostgres-のチームストア)。各コンピューターが学んだことを
  まとめ、チームメイトのナレッジを送り返します

ハブが受け取るのは**ナレッジだけ**です。各コンピューターは自分のセッションを自分の Claude Code、Codex、またはモデル
プロバイダーで記録・分析し、各セッションの要約とプロジェクトのナレッジだけをハブに送ります。トランスクリプト、
プロンプト、ファイルパスはコンピューターに残ります。ハブは何も分析しないので、モデルも API キーも要りません。

## 始める前に

- Docker と Docker Compose が動くサーバー
- `chronicle.example.com` のようなハブの名前（DNS がそのサーバーを指していること）
- ハブを使うコンピューターから届くポート 80 と 443。Caddy が Let's Encrypt から証明書を取得するのにも使います。
  社内ネットワークからしか届かない名前の場合は[自分の証明書を使う](#自分の証明書を使う)を参照してください

## 起動する

空のフォルダーに 3 つのファイルをダウンロードします。

```bash
mkdir chronicle-hub && cd chronicle-hub
base=https://raw.githubusercontent.com/Chatixia-AI/agents-chronicle/main/docker
curl -fsSL "$base/compose.yaml" -o compose.yaml
curl -fsSL "$base/Caddyfile" -o Caddyfile
curl -fsSL "$base/.env.example" -o .env
```

`.env` を埋めます。

```bash
CHRONICLE_DOMAIN=chronicle.example.com   # ハブの名前
CHRONICLE_ADMIN_EMAIL=you@example.com    # 最初の管理者
CHRONICLE_ADMIN_NAME=You
POSTGRES_PASSWORD=...                    # 長くランダムに: openssl rand -hex 24
```

起動して、最初の管理者の招待を確認します。

```bash
docker compose up -d
docker compose logs hub
```

```text
Added You (you@example.com) as this hub's admin. The invite works once, for 7 days:

  In a browser, to open the hub's dashboard:  https://chronicle.example.com/signin?code=ABCD-EFGH-JKLM
  Or on their computer, to join it:           chronicle hub join https://chronicle.example.com --code ABCD-EFGH-JKLM --share knowledge
```

招待は一度だけ表示されます。見逃したときや期限が切れたときは、新しく作ります。

```bash
docker compose exec hub chronicle hub invite you@example.com
```

リンクを開くと、管理者としてダッシュボードを使えます。1 つの招待で開けるブラウザーまたは参加できるコンピューターは
1 つだけです。自分のコンピューターが学んだことも送るには、上のコマンドで 2 つ目の招待を作り、その参加コマンドを
自分のコンピューターで実行します。

ハブに管理者ができるまで、コンテナーは何も提供しません。利用者のいないハブは、届いた人を誰でも管理者として通して
しまうため、`CHRONICLE_ADMIN_EMAIL` なしで起動するとエラーで止まり、何も提供しません。

## チームを招待する

ダッシュボードでは **Team › People** で人を追加し、招待を作ります。サーバーからは次のようにします。

```bash
docker compose exec hub chronicle hub invite "Bob" --email bob@example.com --all-projects
docker compose exec hub chronicle hub invite "Vic" --email vic@example.com --role readonly --project web-app
docker compose exec hub chronicle hub people
```

コンテナー内で実行したコマンドは、ほかのハブのコンピューターでのコマンドと同じく管理者として動きます
（[利用者とロール](devices.md#利用者とロール)）。ダッシュボード経由のリクエストはそうなりません。コンテナーは
`[server] behind_proxy` を設定するので、管理者も含めて、ダッシュボードを開く人は全員サインインします。

コンテナーのハブはあなたのリポジトリでセッションを実行しないので、その git リモートを知りません。参加したら、メンバーは
プロジェクトごとに自分のフォルダーを追加します。追加しないと、そのコンピューターは何も共有しません：
`chronicle hub add-folder ~/work/demo-app --project demo-app`。ほかのフォルダーのセッションはそのコンピューターに残ります
（[ナレッジだけを共有する](devices.md#ナレッジだけを共有する)）。コンピューターが送ったものを取り消すには：
`docker compose exec hub chronicle hub purge bob@example.com --project demo-app`
（[コンピューターが送ったものを取り消す](devices.md#コンピューターが送ったものを取り消す)）。

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
