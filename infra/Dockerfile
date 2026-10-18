FROM python:3.12-slim

# postgresql-client 16 comes from the PostgreSQL apt repository (Debian ships a different major).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y curl gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 PATH=/opt/venv/bin:$PATH
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY config ./config
RUN uv sync --frozen --no-dev

RUN useradd --system --no-create-home craftech
USER craftech
