- **The hub's image is now `ghcr.io/chatixia-ai/interlatch-hub`:** download `compose.yaml` again to move to it
  ([Update](docs/docker.md#update)); a `.env` with the `CHRONICLE_*` names, the data and the volumes stay as they are,
  and `chronicle-hub` gets the same image for now, so a hub that only runs `docker compose pull` keeps updating.
