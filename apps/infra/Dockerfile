FROM node:24-bookworm-slim AS node

FROM python:3.13-slim-bookworm AS build
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /build
COPY package.json package-lock.json ./
COPY apps/frontend/package.json apps/frontend/package.json
COPY specs/package.json specs/package.json
RUN npm ci
COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/.python-version apps/backend/
RUN cd apps/backend && uv sync --locked --no-install-project
COPY specs specs
COPY scripts scripts
COPY apps/backend/app apps/backend/app
COPY apps/frontend apps/frontend
RUN npm run generate && npm run build
RUN cd apps/backend && uv sync --locked --no-dev --no-install-project

FROM python:3.13-slim-bookworm AS runtime
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /build/apps/backend/.venv /app/.venv
COPY --from=build /build/apps/backend/app /app/app
COPY --from=build /build/apps/frontend/dist /app/dist
ENV PATH="/app/.venv/bin:$PATH" STATIC_DIR=/app/dist
USER app
EXPOSE 8000
CMD ["python", "-m", "app.start"]
