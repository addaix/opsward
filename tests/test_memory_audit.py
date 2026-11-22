"""opsward memory-audit: fleet-wide rules stranded in project memory (addaix/opsward#79)."""

from pathlib import Path

from opsward import memory_audit as ma


def _mem(home: Path, slug: str, filename: str, body: str, *, kind="feedback", name=None, description=""):
    folder = home / "projects" / slug / "memory"
    folder.mkdir(parents=True, exist_ok=True)
    front = f"---\nname: {name or filename}\ndescription: {description}\nmetadata:\n  type: {kind}\n---\n"
    (folder / f"{filename}.md").write_text(front + body)


def _home(tmp_path):
    home = tmp_path / ".claude"
    _mem(home, "-w-t-priv", "llm-via-aix", "Always route LLM generation calls through aix, never a vendor SDK directly.")
    _mem(home, "-w-t-kodokan", "aix-for-llm", "Never call a vendor SDK directly: always route LLM generation calls through aix.")
    _mem(home, "-w-t-priv", "priv-golden", "In priv, the CLI golden is re-recorded after each surface change.")
    _mem(home, "-w-t-priv", "old-merge", "Moved to the landing-a-branch skill.", name="old-merge-SUPERSEDED")
    _mem(home, "-w-t-priv", "who-i-am", "Python expert.", kind="user")
    (home / "projects" / "-w-t-priv" / "memory" / "MEMORY.md").write_text("- index\n")
    skill = home / "skills" / "aix-routing"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: aix-routing\ndescription: route LLM generation calls through aix\n---\nbody")
    (home / "CLAUDE.md").write_text("# Global\n")
    return home


def test_the_audit_finds_strandings_duplicates_owners_and_stubs(tmp_path):
    out = ma.audit(home=_home(tmp_path))
    by = {m["name"]: m for m in out["memories"]}
    assert set(by) == {"llm-via-aix", "aix-for-llm", "priv-golden", "old-merge-SUPERSEDED"}  # feedback only, no index
    assert by["llm-via-aix"]["scope"] == "fleet" and by["llm-via-aix"]["owner"] == "skill:aix-routing"
    assert [Path(d).stem for d in by["llm-via-aix"]["duplicates"]] == ["aix-for-llm"]
    assert by["priv-golden"]["scope"] == "project" and not by["priv-golden"]["duplicates"]
    assert by["old-merge-SUPERSEDED"]["stub"] and not by["old-merge-SUPERSEDED"]["owner"]
    assert out["counts"] == {"memories": 4, "projects": 2, "fleet": 2, "with_duplicates": 2, "stubs": 1, "covered": 2}


def test_not_yet_said_by_its_owner(tmp_path):
    out = ma.audit(home=_home(tmp_path), read_owner=lambda owner: "Something else entirely.")
    assert not [m for m in out["memories"] if m["covered"]]


def test_the_page_names_no_home_path_and_puts_fleet_rules_first(tmp_path):
    home = _home(tmp_path)
    page = ma.render(ma.audit(home=home), home=home)
    rows = [line for line in page.splitlines() if line.startswith("| ") and "Memory" not in line]
    assert rows[0].split(" | ")[2] == "fleet" and "delete (stub)" in rows[-1]
    assert str(home) not in page
