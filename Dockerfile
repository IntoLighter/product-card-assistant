FROM ghcr.io/astral-sh/uv:0.9.16-python3.12-bookworm-slim

WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Дополнительные группы зависимостей: отладочный образ передаёт "--group debug"
ARG UV_SYNC_EXTRA=""

# Сначала зависимости — слой кэшируется, пока не меняется uv.lock
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev ${UV_SYNC_EXTRA}
ENV PATH="/srv/.venv/bin:$PATH"

# Затем код и ресурсы: проект не устанавливается, Streamlit запускает app/ui.py
COPY app ./app
COPY resources ./resources

EXPOSE 8501
CMD ["streamlit", "run", "app/ui.py", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
