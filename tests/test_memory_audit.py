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


def test_a_memory_naming_its_own_project_is_kept_with_it_despite_the_lossy_slug(tmp_path):
    """tw_platform's slug is ``...-tw-platform``; the real cwd comes from its transcripts (addaix/opsward#90)."""
    import json

    home = tmp_path / ".claude"
    cwd = "/w/tt/tw_platform"
    slug = ma.project_slug(cwd)
    _mem(home, slug, "deploys", "In tw_platform, deploys go through deploy.py; never rsync by hand.")
    _mem(home, slug, "naming", "The tw-platform CLI golden is re-recorded after each surface change.")
    folder = home / "projects" / slug
    records = [{"type": "mode"}, {"type": "system", "cwd": "/elsewhere"}, {"type": "system", "cwd": cwd}]
    (folder / "s1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")

    assert ma.project_dir(folder) == cwd
    found = ma.memories(home)
    assert {m.project_dir for m in found} == {cwd}
    by = {m.name: ma.classify(m) for m in found}
    assert by["naming"] == ("project", "names its own project (tw_platform)")
    assert by["deploys"][0] == "fleet" and "though it names tw_platform" in by["deploys"][1]


def test_without_transcripts_the_slug_name_still_matches_inside_an_underscored_name(tmp_path):
    m = ma.Memory("p", "-w-tt-tw-platform", "feedback", "n", "", "The tw_platform golden is re-recorded.", "")
    assert ma.project_dir(tmp_path / "missing") == ""
    assert ma.classify(m) == ("project", "names its own project (platform)")
