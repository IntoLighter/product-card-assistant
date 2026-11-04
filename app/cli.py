"""Пакетная генерация карточек из JSON-файлов.

    uv run python -m app.cli examples/*.json --out examples/output
"""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

from app.core.config import Settings
from app.core.llm import LLMError, OpenAICompatibleClient
from app.core.pipeline import generate_card
from app.core.render import to_json, to_markdown
from app.core.validation import InputError, parse_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Черновики карточек товаров КИП из JSON")
    parser.add_argument("inputs", nargs="+", help="JSON-файлы (объект или массив товаров)")
    parser.add_argument("--out", default="examples/output", help="папка для .md и .json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    # Windows-консоль: кириллица без кракозябр
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = Settings.from_env()
    llm = OpenAICompatibleClient(settings)
    ok, status = llm.health()
    if not ok:
        print(f"[ошибка] {status}")
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [p for pattern in args.inputs for p in (glob.glob(pattern) or [pattern])]
    failed = 0

    for path in map(Path, files):
        try:
            items = parse_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as e:
            print(f"[ошибка] {path}: не удалось прочитать файл ({e})")
            failed += 1
            continue
        except InputError as e:
            print(f"[ошибка] {path}: {e}")
            failed += 1
            continue

        for i, raw in enumerate(items, 1):
            stem = path.stem if len(items) == 1 else f"{path.stem}_{i}"
            try:
                card = generate_card(raw, llm, settings.max_attempts, settings.model)
            except (InputError, LLMError) as e:
                print(f"[ошибка] {stem}: {e}")
                failed += 1
                continue
            (out_dir / f"{stem}.md").write_text(to_markdown(card), encoding="utf-8")
            (out_dir / f"{stem}.json").write_text(to_json(card), encoding="utf-8")
            mark = "ok" if card.meta["checks_passed"] else "есть замечания"
            print(f"[{mark}] {stem}: заголовок {card.meta['seo_title_length']} симв., "
                  f"описание {card.meta['seo_description_length']} симв., попыток {card.meta['attempts']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
