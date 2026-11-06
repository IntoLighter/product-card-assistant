"""
Где лежат ресурсы: промпты и шаблоны приборов.

Ресурсы — данные, а не код: их правят без программиста (в будущем и из самой
программы), поэтому они вынесены из пакета в папку resources/ в корне проекта:

    resources/prompts/    тексты промптов (*.txt)
    resources/templates/  шаблоны формы по типам приборов (*.json)

Другую папку можно задать переменной окружения RESOURCES_DIR. Путь читается
при каждом обращении, поэтому значение из .env подхватывается и после импорта.
"""

import os
from pathlib import Path

# app/core/resources.py -> корень проекта (в Docker — /srv)
DEFAULT_RESOURCES_DIR = Path(__file__).resolve().parents[2] / "resources"


def resources_dir() -> Path:
    return Path(os.getenv("RESOURCES_DIR") or DEFAULT_RESOURCES_DIR)


def prompts_dir() -> Path:
    return resources_dir() / "prompts"


def templates_dir() -> Path:
    return resources_dir() / "templates"
