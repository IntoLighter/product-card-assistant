import json

from cli import BatchRunner, expand_patterns
from factories import FakeLLM, make_draft, manometer_data


def test_expand_patterns(tmp_path):
    for name in ["b.json", "a.json", "notes.txt"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")

    assert expand_patterns([str(tmp_path / "*.json")]) == [
        tmp_path / "a.json",
        tmp_path / "b.json",
    ]
    assert expand_patterns([str(tmp_path / "notes.txt")]) == [tmp_path / "notes.txt"]
    # Пустая маска остаётся как есть: чтение сообщит, что файла нет
    assert expand_patterns([str(tmp_path / "*.csv")]) == [tmp_path / "*.csv"]


def test_batch_runner_writes_results_and_counts_failures(tmp_path):
    good = tmp_path / "manometer.json"
    good.write_text(json.dumps(manometer_data(), ensure_ascii=False), encoding="utf-8")
    nameless = tmp_path / "nameless.json"
    nameless.write_text('{"name": ""}', encoding="utf-8")
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    broken = tmp_path / "broken.json"
    broken.write_text("{не json", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    runner = BatchRunner(llm=FakeLLM(make_draft()), out_dir=out_dir, max_attempts=1)
    for path in [good, nameless, array, broken, tmp_path / "absent.json"]:
        runner.run_file(path)

    assert sorted(path.name for path in out_dir.iterdir()) == [
        "manometer.json",
        "manometer.md",
    ]
    # Товар без названия, массив вместо объекта, битый JSON, отсутствующий файл
    assert runner.failures == 4
