# The site as static files, served by Caddy, which also proxies /api/ to Django:
# there is no Node server in production. Built and pushed to GHCR by
# .github/workflows/deploy.yml; see deploy/README.md.
FROM node:24-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/out /srv/site
