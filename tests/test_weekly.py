"""opsward weekly: the setup's five numbers and one proposed change (addaix/opsward#80)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from opsward import weekly as w

NOW = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)


def _use(name, cwd="/w/pkg", **args):
    return {"type": "assistant", "cwd": cwd, "message": {"content": [{"type": "tool_use", "name": name, "input": args}]}}


def _home(tmp_path):
    home = tmp_path / ".claude"
    proj = home / "projects" / "-w-pkg"
    proj.mkdir(parents=True)
    records = [
        _use("Skill", skill="fleet-protocol"),
        _use("Write", file_path="/w/pkg/new.py"),
        _use("Read", file_path="/w/other/CLAUDE.md"),
        _use("Edit", file_path="/w/other/mod.py"),
        _use("Edit", file_path="/w/third/mod.py"),
    ]
    (proj / "s1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\nnot json\n")
    for name in ("fleet-protocol", "unused"):
        (home / "skills" / name).mkdir(parents=True)
        (home / "skills" / name / "SKILL.md").write_text("---\nname: x\n---\n")
    return home


def _claude_md(path: Path) -> bool:
    return path.as_posix() in ("/w/other/CLAUDE.md", "/w/third/CLAUDE.md")


def test_the_five_numbers_and_the_history(tmp_path, monkeypatch):
    monkeypatch.setattr(w.Path, "is_file", lambda self: _claude_md(self) or Path.exists(self))
    events = [
        {"ts": "2026-11-20T10:00:00", "event": "trigger-prompt"},
        {"ts": "2026-11-20T10:05:00", "event": "trigger-fix-commit"},
        {"ts": "2026-11-20T10:06:00", "event": "writeback-seen"},
        {"ts": "2026-09-01T10:00:00", "event": "trigger-prompt"},  # outside the window
    ]
    history = tmp_path / "hist"
    first = w.weekly(home=str(_home(tmp_path)), search=lambda since: 6, events=events, history=history, now=NOW)
    assert first["numbers"] == {
        "search_before_write": 1.0, "skill_use": 0.5, "claude_md_before_edit": 0.5,
        "component_issues": 1.4, "corrections": 0.5,
    }  # fmt: skip
    assert first["skill_use"]["never_invoked"] == ["unused"] and first["previous"] is None
    assert (history / "2026-11-22.json").is_file()

    later = datetime(2026, 11, 29, 12, tzinfo=timezone.utc)
    second = w.weekly(home=str(_home(tmp_path / "b")), search=lambda since: 2, events=events, history=history, now=later)
    assert second["previous"]["numbers"]["component_issues"] == 1.4
    assert second["proposal"]["key"] == "component_issues"  # fell from 1.4 to about 0.47 a week
    page = w.render(second)
    assert "| 4 | Component issues per week | 0.47 | 1.4 | higher |" in page and "proposed target condition" in page


def test_a_failing_issue_search_is_reported_not_raised(tmp_path):
    def broken(since):
        raise RuntimeError("gh: not logged in")

    out = w.weekly(home=str(tmp_path), search=broken, events=[], history=tmp_path / "h", save=False, now=NOW)
    assert out["component_issues"]["error"].startswith("gh") and out["numbers"]["component_issues"] is None
    assert "not counted" in w.render(out) and not (tmp_path / "h").exists()
