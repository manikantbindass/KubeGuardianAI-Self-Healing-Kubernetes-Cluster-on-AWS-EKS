import importlib.util
from pathlib import Path


def test_link_validator_rejects_missing_and_outside_paths(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "validate_repository.py"
    spec = importlib.util.spec_from_file_location("validator", script)
    assert spec and spec.loader
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    (tmp_path / "present.md").write_text("# Present\n", encoding="utf-8")
    page = tmp_path / "README.md"
    page.write_text(
        "[valid](present.md) [remote](https://example.invalid/) "
        "[missing](missing.md) [outside](../outside.md)\n",
        encoding="utf-8",
    )
    errors = validator.broken_links(page, tmp_path)
    assert len(errors) == 2
    assert any("missing.md" in error for error in errors)
    assert any("outside.md" in error for error in errors)
