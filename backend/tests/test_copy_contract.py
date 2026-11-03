import ast
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

BACKEND: Final = Path(__file__).resolve().parents[1]
REPO: Final = BACKEND.parent
COPY_TS: Final = REPO / "app" / "src" / "renderer" / "src" / "lib" / "copy.ts"
RENDERER: Final = REPO / "app" / "src" / "renderer" / "src"
LINES_JSON: Final = REPO / "assets" / "lines.json"

SKIP_DIRS: Final = frozenset({".venv", "__pycache__", "tests", "smoke", ".mypy_cache"})
KEY_SHAPE: Final = re.compile(r"^[a-z0-9_]+(\.[A-Za-z0-9_]+)*$")
PLACEHOLDER: Final = re.compile(r"\[([A-Za-z_]+)\]")
ENTRY_KEY: Final = re.compile(r"^ {2}(?:'([^']+)'|([A-Za-z_]+)):", re.MULTILINE)
LITERAL_TEMPLATE_KEYS: Final = frozenset({"claim.prompt", "claim.voice_hint"})
MOMENT_CALLS: Final = frozenset({"emit_moment", "_fill_moment"})
NOTICE_CALLS: Final = frozenset({"_notify", "notice_json"})
BANK_PLACEHOLDERS: Final = frozenset(
    {"unit", "turns", "beaten", "downed", "badge", "player", "HP"}
)
ENEMY_TYPES: Final = ("aswang", "tikbalang", "kapre", "manananggal", "duwende")
EDGES: Final = ("north", "east", "south", "west")


def backend_sources() -> Iterator[Path]:
    for path in sorted(BACKEND.rglob("*.py")):
        if SKIP_DIRS.isdisjoint(path.relative_to(BACKEND).parts):
            yield path


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def copy_keys() -> set[str]:
    source = COPY_TS.read_text(encoding="utf-8")
    start = source.index("const entries = {")
    end = source.index("} as const satisfies")
    return {m.group(1) or m.group(2) for m in ENTRY_KEY.finditer(source[start:end])}


def call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def first_string(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant):
        value = node.args[0].value
        if isinstance(value, str):
            return value
    return None


def copy_error_classes(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Attribute)
                and isinstance(inner.ctx, ast.Store)
                and inner.attr == "copy_key"
            ):
                found.add(node.name)
    return found


def backend_notice_keys() -> dict[str, set[str]]:
    trees = {path: parse(path) for path in backend_sources()}
    error_classes = {
        name for tree in trees.values() for name in copy_error_classes(tree)
    }
    keys: dict[str, set[str]] = {}

    def add(key: str, path: Path) -> None:
        keys.setdefault(key, set()).add(path.relative_to(BACKEND).as_posix())

    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node)
                literal = first_string(node)
                if literal is not None and (
                    name in error_classes or name in NOTICE_CALLS
                ):
                    add(literal, path)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                value = node.value
                for target in targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id.endswith("_KEY")
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and KEY_SHAPE.match(value.value)
                    ):
                        add(value.value, path)
            elif isinstance(node, ast.FunctionDef) and node.name.endswith("_key"):
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.Return)
                        and isinstance(inner.value, ast.Constant)
                        and isinstance(inner.value.value, str)
                    ):
                        add(inner.value.value, path)
    return keys


def bank() -> dict[str, list[dict[str, str]]]:
    data = json.loads(LINES_JSON.read_text(encoding="utf-8"))
    moments: dict[str, list[dict[str, str]]] = data["moments"]
    return moments


def sent_moments() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}

    def add(moment: str, path: Path) -> None:
        found.setdefault(moment, set()).add(path.relative_to(BACKEND).as_posix())

    for path in backend_sources():
        tree = parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node)
                literal = first_string(node)
                if literal is not None and (
                    name in MOMENT_CALLS
                    or (name == "fill" and path.parent.name == "gm")
                ):
                    add(literal, path)
            elif isinstance(node, ast.FunctionDef) and node.name == "pick_moment":
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.Return)
                        and isinstance(inner.value, ast.Constant)
                        and isinstance(inner.value.value, str)
                    ):
                        add(inner.value.value, path)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                value = node.value
                if "REQUIRED_MOMENTS" in names and isinstance(value, ast.Tuple):
                    for element in value.elts:
                        if isinstance(element, ast.Constant) and isinstance(
                            element.value, str
                        ):
                            add(element.value, path)
                if "moment" in names and isinstance(value, ast.IfExp):
                    for branch in (value.body, value.orelse):
                        if isinstance(branch, ast.Constant) and isinstance(
                            branch.value, str
                        ):
                            add(branch.value, path)
            elif (
                isinstance(node, ast.Return)
                and path.name == "recap.py"
                and isinstance(node.value, ast.Tuple)
                and node.value.elts
                and isinstance(node.value.elts[0], ast.Constant)
                and isinstance(node.value.elts[0].value, str)
            ):
                add(node.value.elts[0].value, path)
    for enemy in ENEMY_TYPES:
        found.setdefault(f"spawn_{enemy}", set()).add("gm/narrator.py")
    for edge in EDGES:
        found.setdefault(f"spawn_aswang_{edge}", set()).add("gm/narrator.py")
    return found


def placeholders(text: str) -> list[str]:
    return sorted(PLACEHOLDER.findall(text))


def test_copy_deck_parse_finds_the_deck() -> None:
    keys = copy_keys()
    assert len(keys) > 300
    assert {"cmd.unknown", "err.generic", "win", "lose"} <= keys


def test_backend_notice_scan_finds_the_known_keys() -> None:
    found = backend_notice_keys()
    expected = {
        "cam.busy",
        "cmd.unknown",
        "err.generic",
        "endturn.checking",
        "net.down",
    }
    assert expected <= set(found)
    assert {"unit.lost", "unit.found", "summon.stack", "summon.which"} <= set(found)
    assert {"summon.kubo_first", "summon.need_units"} <= set(found)


def test_every_notice_key_the_backend_can_send_exists_in_copy() -> None:
    keys = copy_keys()
    missing = {
        key: sorted(files)
        for key, files in backend_notice_keys().items()
        if key not in keys
    }
    assert missing == {}


def test_backend_never_sends_the_literal_template_keys_as_notices() -> None:
    assert LITERAL_TEMPLATE_KEYS.isdisjoint(backend_notice_keys())


def test_every_line_bank_moment_has_filled_tl_and_en() -> None:
    for moment, lines in bank().items():
        assert lines, moment
        for index, line in enumerate(lines):
            where = f"{moment}[{index}]"
            assert line["tl"].strip(), f"{where} tl"
            assert line["en"].strip(), f"{where} en"
            assert line["mood"] in {"kalmado", "kaba", "takot", "tagumpay", "umaga"}, (
                where
            )


def test_line_bank_placeholders_match_between_tl_and_en() -> None:
    for moment, lines in bank().items():
        for index, line in enumerate(lines):
            where = f"{moment}[{index}]"
            assert placeholders(line["tl"]) == placeholders(line["en"]), where


def test_line_bank_placeholders_are_ones_the_backend_fills() -> None:
    for moment, lines in bank().items():
        for index, line in enumerate(lines):
            used = set(placeholders(line["tl"])) | set(placeholders(line["en"]))
            assert used <= BANK_PLACEHOLDERS, f"{moment}[{index}] {sorted(used)}"


def test_moment_scan_finds_the_known_moments() -> None:
    found = sent_moments()
    expected = {
        "night_start",
        "unit_lost",
        "badge_earned",
        "recap_win",
        "spawn_kapre",
        "hit",
    }
    assert expected <= set(found)


def test_every_moment_the_backend_sends_exists_in_the_bank() -> None:
    available = set(bank())
    missing = {
        m: sorted(files) for m, files in sent_moments().items() if m not in available
    }
    assert missing == {}


def test_every_say_key_in_the_renderer_exists_in_copy() -> None:
    keys = copy_keys()
    call = re.compile(r"\b(?:say|t)\(([^()]*)\)")
    literal = re.compile(r"'([a-z0-9_]+(?:\.[A-Za-z0-9_]+)+)'")
    missing: list[str] = []
    for path in sorted(RENDERER.rglob("*.ts*")):
        if path.name == "copy.ts":
            continue
        text = path.read_text(encoding="utf-8")
        for match in call.finditer(text):
            for key in literal.findall(match.group(1)):
                if key not in keys:
                    missing.append(f"{path.name}: {key}")
    assert missing == []


@pytest.mark.parametrize("key", sorted(LITERAL_TEMPLATE_KEYS))
def test_literal_template_keys_exist(key: str) -> None:
    assert key in copy_keys()
