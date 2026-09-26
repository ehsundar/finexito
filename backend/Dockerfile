# Django behind gunicorn. Built and pushed to GHCR by .github/workflows/deploy.yml; see deploy/README.md.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# Dependencies first, so a code-only change reuses this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# WhiteNoise serves these from inside the container; nothing else needs them.
RUN python manage.py collectstatic --noinput

# gunicorn's control server keeps its socket under $HOME, so the user needs one.
RUN useradd --system --create-home --uid 1000 app
# Where the `storage` volume mounts. A new volume copies this directory's owner,
# so the app can write uploads without any setup on the server.
RUN install -d -o app -g app /srv/storage
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
