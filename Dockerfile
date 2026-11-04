FROM ghcr.io/astral-sh/uv:0.9.16-python3.12-bookworm-slim

WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Сначала только зависимости — слой кэшируется, пока не меняется uv.lock
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Затем код и установка самого пакета app
COPY app ./app
COPY examples ./examples
RUN uv sync --frozen --no-dev
ENV PATH="/srv/.venv/bin:$PATH"

EXPOSE 8501
CMD ["streamlit", "run", "app/ui.py", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
