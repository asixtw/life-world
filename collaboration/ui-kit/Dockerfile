# 建構 context 固定為 collaboration/ui-kit，避免把正式 App／DB 帶入映像。
FROM node:24.22.2-bookworm-slim AS dependencies
WORKDIR /site
ENV CI=true
RUN npm install --global pnpm@12.16.1 \
    && test "$(pnpm --version)" = "12.16.1"
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM dependencies AS source
# .dockerignore 僅允許必要來源、fixture 與資產；沒有憑證或環境檔。
COPY . .

FROM source AS verify
RUN pnpm test

FROM verify AS build
# 本機 docker build 也不可繞過同一份 React 測試。
RUN pnpm run build

FROM python:3.12-slim AS server-dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY tools/web-requirements.lock /tmp/web-requirements.lock
RUN python -m venv /opt/venv && pip install -r /tmp/web-requirements.lock

FROM server-dependencies AS server-verify
COPY tools/web_server.py tools/test_web_server.py ./
# 合成 upstream 測試必須先通過；不向 GCP mint token 或連實際資料庫。
RUN python -m unittest -q test_web_server

FROM server-dependencies AS runtime
ARG VCS_REF=local-unpublished
ARG LIFEWORLD_WEB_API_ORIGIN=
ENV LIFEWORLD_WEB_API_ORIGIN=${LIFEWORLD_WEB_API_ORIGIN}
LABEL org.opencontainers.image.title="Life World Web main: business gateway and UI gallery" \
      org.opencontainers.image.revision="${VCS_REF}"
RUN groupadd --gid 10001 lifeworld && useradd --uid 10001 --gid 10001 --no-create-home lifeworld
COPY --from=build /site/dist /srv/gallery
COPY --from=server-verify /srv/web_server.py /srv/web_server.py
# 不複製原始碼、API／DB driver 或憑證；未配置 upstream 時只提供原 gallery。
USER 10001:10001
EXPOSE 8080
CMD ["python", "web_server.py"]
