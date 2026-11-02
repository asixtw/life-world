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

FROM nginxinc/nginx-unprivileged:1.28-alpine AS runtime
ARG VCS_REF=local-unpublished
LABEL org.opencontainers.image.title="Life World UI candidate staging" \
      org.opencontainers.image.revision="${VCS_REF}"
COPY cloud-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site/dist /usr/share/nginx/html
# 只留下靜態編譯產物；使用映像既有的非 root 使用者及 /tmp PID。
RUN nginx -t
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
