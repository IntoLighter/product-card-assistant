FROM ghcr.io/astral-sh/uv:0.9.16-python3.12-bookworm-slim

WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Сначала зависимости без самого проекта — слой кэшируется, пока не меняется uv.lock
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/srv/.venv/bin:$PATH"

# Затем код и ресурсы, и проект ставится в окружение в режиме редактирования:
# пакет app остаётся в /srv/app (рядом с resources, а в отладке — смонтированный код)
COPY app ./app
COPY resources ./resources
RUN uv sync --frozen --no-dev

EXPOSE 8501
CMD ["streamlit", "run", "app/ui.py"]
