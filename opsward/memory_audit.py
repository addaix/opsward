"""Memory audit: fleet-wide rules stranded in project-local auto-memory, and who should own them.

Claude Code's auto-memory is keyed by working directory: a ``feedback`` memory written in one
project loads only in sessions started there. A rule that holds for every project is stranded
in that one. This audit lists every memory of the chosen kinds, then for each one:

- **scope**: ``project`` or ``fleet``, with the reason (:func:`classify`, a heuristic; pass
  ``classify=`` to use a judge instead);
- **duplicates**: memories in *other* directories that say nearly the same thing
  (:func:`similarity`, lexical, replaceable);
- **owner**: for a fleet-wide one, the installed skill whose name and description match it
  best, else ``~/.claude/CLAUDE.md``, and whether the owner already says it;
- **stub**: a memory that only says it moved elsewhere, listed for deletion.

Report-only: it never writes, moves or deletes a memory. The user curates the table.

>>> parse_frontmatter("---\\nname: x\\nmetadata:\\n  type: feedback\\n---\\nbody")
({'name': 'x', 'type': 'feedback'}, 'body')
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DFLT_CLAUDE_HOME = Path("~/.claude")
DFLT_KINDS = ("feedback",)
KINDS = ("user", "feedback", "project", "reference")
INDEX_FILE = "MEMORY.md"
#: Two memories in different directories at or above this similarity are reported as duplicates.
DUPLICATE_AT = 0.45
#: A skill must match a fleet-wide memory at least this well to be proposed as its owner.
OWNER_AT = 0.08
#: Share of a memory's distinctive words its owner must already hold to say "already there".
COVERED_AT = 0.6
_WORD = re.compile(r"[a-z][a-z0-9_-]{2,}")
STOPWORDS = frozenset(
    "the and for that this with are was were not but you your they them their its into from "
    "when what which who how why use used using than then there here have has had any all "
    "one two can could should would will must may might only also more most less such each "
    "every other same over under about after before while where does did done just like "
    "user prefers prefer always never rule why apply because instead so it is be an of to in "
    "on at by as or if no do".split()
)  # fmt: skip
STUB_PATTERN = re.compile(
    r"\b(moved to|superseded|now (?:lives )?in|see instead|replaced by|lives in)\b", re.IGNORECASE
)
#: Words that mark a rule as a habit for every project.
FLEET_CUES = re.compile(
    r"\b(always|never|every (?:project|repo|package|session)|in general|whenever|by default|"
    r"from now on|across (?:the )?(?:fleet|projects|repos))\b",
    re.IGNORECASE,
)


@dataclass
class Memory:
    """One memory file."""

    path: str
    project: str  # the project directory's slug
    kind: str
    name: str
    description: str
    body: str
    modified: str
    scope: str = ""
    reason: str = ""
    duplicates: list = field(default_factory=list)
    owner: str = ""
    owner_score: float = 0.0
    covered: bool = False
    stub: bool = False

    @property
    def text(self) -> str:
        return f"{self.name}\n{self.description}\n{self.body}"


# --- reading --------------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """``(fields, body)``: flat ``key: value`` fields of a ``---`` block, nested ``metadata``
    keys lifted to the top (``metadata: type: feedback`` gives ``type``)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fields: dict = {}
    for line in text[3:end].splitlines():
        key, sep, value = line.strip().partition(":")
        if sep and value.strip() and key.strip():
            fields.setdefault(key.strip(), value.strip().strip("\"'"))
    return fields, text[end + 4 :].lstrip("\n")


def _kind_of(fields: Mapping, filename: str) -> str:
    kind = str(fields.get("type", "")).strip().lower()
    if kind in KINDS:
        return kind
    prefix = filename.split("_", 1)[0].lower()
    return prefix if prefix in KINDS else "unknown"


def project_name(slug: str) -> str:
    """The project a directory slug names: its last path part.

    >>> project_name("-Users-me-Dropbox-py-proj-t-priv")
    'priv'
    """
    return slug.rstrip("-").rsplit("-", 1)[-1] or slug


def memories(home: str | os.PathLike | None = None, *, kinds: Iterable[str] = DFLT_KINDS) -> list[Memory]:
    """Every memory of ``kinds`` under ``home``'s project folders (``MEMORY.md`` indexes excluded)."""
    base = Path(home or DFLT_CLAUDE_HOME).expanduser() / "projects"
    kinds = set(kinds)
    out = []
    for path in sorted(base.glob("*/memory/*.md")):
        if path.name == INDEX_FILE:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fields, body = parse_frontmatter(text)
        kind = _kind_of(fields, path.stem)
        if kinds and kind not in kinds:
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
        out.append(Memory(
            str(path), path.parent.parent.name, kind, str(fields.get("name") or path.stem),
            str(fields.get("description") or ""), body.strip(), modified,
        ))  # fmt: skip
    return out


def skills(dirs: Iterable[str | os.PathLike]) -> dict[str, str]:
    """``{name: "name description"}`` of the skills under ``dirs`` (``*/SKILL.md``)."""
    out = {}
    for d in dirs:
        for path in sorted(Path(d).expanduser().glob("*/SKILL.md")):
            fields, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            name = str(fields.get("name") or path.parent.name)
            out.setdefault(path.parent.name, f"{name} {fields.get('description', '')}")
    return out


# --- judging --------------------------------------------------------------------------------


def words(text: str) -> set[str]:
    """The distinctive words of ``text``: lowercase, three letters or more, no stopwords.

    >>> sorted(words("Always route LLM calls through aix, never directly."))
    ['aix', 'calls', 'directly', 'llm', 'route', 'through']
    """
    return {w for w in _WORD.findall(text.lower()) if w not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    """Jaccard similarity of two texts' distinctive words.

    >>> similarity("prefer the storage facade dol", "the dol storage facade, always")
    1.0
    >>> similarity("route calls through aix", "route storage through dol")
    0.333
    """
    x, y = words(a), words(b)
    return round(len(x & y) / len(x | y), 3) if x and y else 0.0


def classify(memory: Memory) -> tuple[str, str]:
    """``(scope, reason)``: ``project`` when the memory names its own project (and is not
    phrased as a habit), else ``fleet`` or ``project`` by its wording.

    >>> m = Memory("p", "-x-t-priv", "feedback", "n", "", "Always route LLM calls through aix.", "")
    >>> classify(m)
    ('fleet', "worded as a habit ('Always') and does not name priv")
    >>> classify(Memory("p", "-x-t-priv", "feedback", "n", "", "In priv, the CLI golden must be re-recorded.", ""))
    ('project', 'names its own project (priv)')
    """
    own = project_name(memory.project).lower()
    mentions_own = len(own) >= 3 and re.search(rf"\b{re.escape(own)}\b", memory.text.lower()) is not None
    cue = FLEET_CUES.search(memory.text)
    if mentions_own and not cue:
        return "project", f"names its own project ({own})"
    if cue and not mentions_own:
        return "fleet", f"worded as a habit ({cue.group(0)!r}) and does not name {own}"
    if cue:
        return "fleet", f"worded as a habit ({cue.group(0)!r}), though it names {own}: check"
    return "project", "no habit wording; kept with its project unless you say otherwise"


def is_stub(memory: Memory, *, short: int = 400, head: int = 200) -> bool:
    """A memory that says it moved: the marker in its name or opening, or anywhere in a short one.

    >>> is_stub(Memory("p", "x", "feedback", "old-rule-SUPERSEDED", "", "x " * 400, ""))
    True
    >>> is_stub(Memory("p", "x", "feedback", "rule", "", "Prefer dol. " * 50 + "It replaced by hand.", ""))
    False
    """
    opening = f"{memory.name}\n{memory.description}\n{memory.body[:head]}"
    return bool(STUB_PATTERN.search(opening)) or (len(memory.body) < short and bool(STUB_PATTERN.search(memory.text)))


def _owner(memory: Memory, owners: Mapping[str, str]) -> tuple[str, float]:
    best, score = "", 0.0
    for name, text in owners.items():
        s = similarity(memory.text, text)
        if s > score:
            best, score = name, s
    return best, score


def _covered(memory: Memory, owner_text: str) -> bool:
    mine, theirs = words(memory.body or memory.description), words(owner_text)
    return bool(mine) and len(mine & theirs) / len(mine) >= COVERED_AT


# --- the audit ------------------------------------------------------------------------------


def audit(
    *,
    home: str | os.PathLike | None = None,
    kinds: Iterable[str] = DFLT_KINDS,
    found: Iterable[Memory] | None = None,
    skills_dirs: Iterable[str | os.PathLike] | None = None,
    global_claude_md: str | os.PathLike | None = None,
    read_owner: Callable[[str], str] | None = None,
    classify: Callable[[Memory], tuple[str, str]] = classify,
    similarity: Callable[[str, str], float] = similarity,
    duplicate_at: float = DUPLICATE_AT,
    owner_at: float = OWNER_AT,
) -> dict:
    """Audit the memories (``found``, default: :func:`memories` of ``home`` and ``kinds``).

    ``read_owner(owner)`` returns an owner's text, to say whether it already holds the rule
    (default: the skill's ``SKILL.md``, or the global ``CLAUDE.md``).
    """
    claude_home = Path(home or DFLT_CLAUDE_HOME).expanduser()
    mems = list(found) if found is not None else memories(claude_home, kinds=kinds)
    skills_dirs = list(skills_dirs) if skills_dirs is not None else [claude_home / "skills"]
    owners = skills(skills_dirs)
    claude_md = Path(global_claude_md or claude_home / "CLAUDE.md").expanduser()

    def default_read(owner: str) -> str:
        path = claude_md if owner == "CLAUDE.md" else next(
            (Path(d).expanduser() / owner / "SKILL.md" for d in skills_dirs if (Path(d).expanduser() / owner / "SKILL.md").is_file()),
            None,
        )  # fmt: skip
        try:
            return path.read_text(encoding="utf-8", errors="replace") if path else ""
        except OSError:
            return ""

    read_owner = read_owner or default_read
    for i, m in enumerate(mems):
        m.stub = is_stub(m)
        m.scope, m.reason = classify(m)
        for other in mems[i + 1 :]:
            if other.project != m.project and similarity(m.text, other.text) >= duplicate_at:
                m.duplicates.append(other.path)
                other.duplicates.append(m.path)
        if m.scope == "fleet" and not m.stub:
            name, score = _owner(m, owners)
            m.owner, m.owner_score = (f"skill:{name}", score) if score >= owner_at else ("CLAUDE.md", score)
            m.covered = _covered(m, read_owner(m.owner.removeprefix("skill:")))
    projects = {m.project for m in mems}
    return {
        "memories": [asdict(m) for m in mems],
        "counts": {
            "memories": len(mems), "projects": len(projects),
            "fleet": sum(m.scope == "fleet" for m in mems), "with_duplicates": sum(bool(m.duplicates) for m in mems),
            "stubs": sum(m.stub for m in mems), "covered": sum(m.covered for m in mems),
        },
    }  # fmt: skip


def render(result: Mapping, *, home: str | os.PathLike | None = None) -> str:
    """The audit as a markdown page: fleet-wide memories and their proposed owner first."""
    base = str(Path(home or DFLT_CLAUDE_HOME).expanduser() / "projects") + os.sep
    c = result["counts"]
    lines = [
        f"# Memory audit: {c['memories']} memories in {c['projects']} project folders",
        "",
        f"{c['fleet']} read as fleet-wide, {c['with_duplicates']} have a near-duplicate in another folder, "
        f"{c['stubs']} are stubs, {c['covered']} are already said by their proposed owner. Report-only: nothing was changed.",
        "",
        "| Memory | Folder | Scope | Proposed owner | Already there | Duplicates | Why |",
        "|---|---|---|---|---|---|---|",
    ]
    order = {"fleet": 0, "project": 1}
    for m in sorted(result["memories"], key=lambda m: (m["stub"], order.get(m["scope"], 2), m["project"], m["name"])):
        owner = "delete (stub)" if m["stub"] else (m["owner"] or "")
        dups = ", ".join(Path(d).stem for d in m["duplicates"]) or ""
        lines.append(
            f"| {m['name']} | {project_name(m['project'])} | {m['scope']} | {owner} | "
            f"{'yes' if m['covered'] else ''} | {dups} | {m['reason']} |"
        )
    return "\n".join(lines).replace(base, "") + "\n"
