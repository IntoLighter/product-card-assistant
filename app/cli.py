"""
Пакетная генерация карточек из JSON-файлов.

    uv run python app/cli.py examples/*.json --out examples/output
"""

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from core.config import Settings
from core.llm import LLMClient, LLMError, OpenAICompatibleClient
from core.pipeline import generate_card
from core.render import to_json, to_markdown
from core.validation import InputError, RawProduct, parse_json

EXIT_OK = 0
EXIT_HAS_FAILURES = 1
EXIT_LLM_UNAVAILABLE = 2

GLOB_CHARS = frozenset("*?[")


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_console()  # до argparse: иначе кириллица в --help выводится кракозябрами
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    settings = Settings()
    llm = OpenAICompatibleClient(settings)
    status = llm.check_server()
    if not status.ready:
        print(f"[ошибка] {status.message}")
        return EXIT_LLM_UNAVAILABLE

    args.out.mkdir(parents=True, exist_ok=True)
    runner = BatchRunner(llm=llm, out_dir=args.out, max_attempts=settings.max_attempts)
    for path in expand_patterns(args.inputs):
        runner.run_file(path)
    return EXIT_HAS_FAILURES if runner.failures else EXIT_OK


@dataclass
class BatchRunner:
    """Обрабатывает файлы по одному и считает неудачи, не прерываясь на первой."""

    llm: LLMClient
    out_dir: Path
    max_attempts: int
    failures: int = 0

    def run_file(self, path: Path) -> None:
        try:
            raw = parse_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            self._fail(str(path), f"не удалось прочитать файл ({error})")
            return
        except InputError as error:
            self._fail(str(path), str(error))
            return

        self._run_product(raw, path.stem)

    def _run_product(self, raw: RawProduct, stem: str) -> None:
        try:
            card = generate_card(raw, self.llm, max_attempts=self.max_attempts)
        except (InputError, LLMError) as error:
            self._fail(stem, str(error))
            return

        (self.out_dir / f"{stem}.md").write_text(to_markdown(card), encoding="utf-8")
        (self.out_dir / f"{stem}.json").write_text(to_json(card), encoding="utf-8")
        verdict = "ok" if card.meta.checks_passed else "есть замечания"
        print(
            f"[{verdict}] {stem}: заголовок {card.meta.seo_title_length} симв., "
            f"описание {card.meta.seo_description_length} симв., "
            f"попыток {card.meta.attempts}"
        )

    def _fail(self, where: str, message: str) -> None:
        self.failures += 1
        print(f"[ошибка] {where}: {message}")


def expand_patterns(patterns: Sequence[str]) -> list[Path]:
    """
    Раскрывает маски вида examples/*.json.

    PowerShell, в отличие от bash, сам их не раскрывает.
    """
    paths: list[Path] = []
    for pattern in patterns:
        path = Path(pattern)
        if GLOB_CHARS.isdisjoint(path.name):
            paths.append(path)
        else:
            # Если по маске ничего нет, оставляем её как есть:
            # чтение файла сообщит об ошибке
            paths.extend(sorted(path.parent.glob(path.name)) or [path])
    return paths


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="product-cards", description="Черновики карточек товаров КИП из JSON"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="JSON-файлы или маски (в каждом файле один товар)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("examples/output"),
        help="папка для .md и .json",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="подробный лог генерации"
    )
    return parser.parse_args(argv)


def _use_utf8_console() -> None:
    """
    Переключает вывод на UTF-8.

    В Windows при выводе в канал кодировка по умолчанию не UTF-8, и кириллица ломается.
    """
    for stream in (sys.stdout, sys.stderr):  # stderr — для логов
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
