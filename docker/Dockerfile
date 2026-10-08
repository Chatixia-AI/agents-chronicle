# Chronicle's hub in a container (docs/docker.md). The release workflow builds it with CHRONICLE_VERSION set and
# publishes it as ghcr.io/chatixia-ai/chronicle-hub. Built without it, it installs the latest release from PyPI; a
# wheel in docker/wheels/ is installed instead, to try a change before it is released:
#   uv build --wheel -o docker/wheels && docker build -t chronicle-hub docker
FROM python:3.14.7-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d

ARG CHRONICLE_VERSION=
LABEL org.opencontainers.image.title="Chronicle hub" \
      org.opencontainers.image.description="A team's hub for Chronicle: what its coding agents learned, without the transcripts" \
      org.opencontainers.image.source="https://github.com/Chatixia-AI/agents-chronicle" \
      org.opencontainers.image.licenses="MIT"

COPY wheels/ /tmp/wheels/
RUN set -e; \
    wheel=$(find /tmp/wheels -name 'agents_chronicle-*.whl' | head -n 1); \
    if [ -n "$wheel" ]; then spec="$wheel[team]"; \
    else spec="agents-chronicle[team]${CHRONICLE_VERSION:+==$CHRONICLE_VERSION}"; fi; \
    pip install --no-cache-dir --root-user-action=ignore "$spec"; \
    rm -rf /tmp/wheels; \
    useradd --create-home --uid 1000 chronicle; \
    mkdir /data; \
    chown chronicle:chronicle /data

# CHRONICLE_CONTAINER: the dashboard's Update button says to pull a new image instead of upgrading in place
ENV CHRONICLE_HOME=/data \
    CHRONICLE_CONTAINER=1 \
    PYTHONUNBUFFERED=1
USER chronicle
WORKDIR /data
VOLUME /data
EXPOSE 11524

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % (os.environ.get('CHRONICLE_PORT') or '11524'), timeout=4)"]

CMD ["chronicle", "container"]
