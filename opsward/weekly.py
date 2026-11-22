"""The weekly look: the agent setup's five numbers, against last week, and one proposed change.

The ``setup-self-improvement`` loop asks for one improvement a week, chosen from five numbers
and passed through a human gate. This module prints the numbers; the user picks the change.
It only reads, and the only thing it writes is its own history (one JSON file per run).

The five numbers, over the last ``days`` (30 by default):

1. **Search before write**: of the new source files an agent wrote, the share written after
   the session had searched what the fleet already has (an Explore agent, a search skill
   such as ``fleet-protocol``, or ``ir``/``projreg``/``priv find``/``gh search`` in Bash).
   Local greps are counted beside it as context: agents run them in nearly every session.
   A file counts as new when the session writes it without having read or edited it first.
2. **Skills never invoked**: the share of installed skills no session invoked (with the
   invocation count per skill). Never-invoked skills are candidates for name-only or
   deletion, not for a longer description.
3. **CLAUDE.md before edit**: of the packages a session edited, the share whose nearest
   ``CLAUDE.md`` the session had loaded first (its cwd is inside the package, or it read the
   file before the first edit).
4. **Component issues per week**: issues titled ``Component: ...`` the owner filed.
5. **Corrections written back**: ``writeback-seen`` events over the triggers (``trigger-prompt``,
   ``trigger-fix-commit``) in the fix-at-source hook's event log.

Only metadata is read: tool names, file paths, skill names, timestamps. Never prompt or file
text. Every source is a keyword argument (``sessions``, ``skills_dirs``, ``search``,
``events``, ``history``), so a caller or a test can point it elsewhere.

>>> NUMBERS[0].key, NUMBERS[1].better
('search_before_write', 'lower')
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePath

DFLT_DAYS = 30
DFLT_CLAUDE_HOME = Path("~/.claude")
DFLT_EVENTS = Path("~/.local/state/fix-at-source/events.jsonl")
EVENTS_ENVVAR = "FIX_AT_SOURCE_LOG"
HISTORY_ENVVAR = "OPSWARD_WEEKLY_DIR"
DFLT_HISTORY = Path("~/.local/share/opsward/weekly")
SOURCE_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".swift", ".go",
    ".kt", ".java", ".rb", ".sh", ".c", ".cc", ".cpp", ".h",
)  # fmt: skip
#: A search of what the fleet already has (the fleet-protocol meaning): an Explore agent, a
#: search skill, or a fleet search command at the start of a Bash command (not after a pipe).
SEARCH_AGENTS = ("Explore",)
SEARCH_SKILLS = ("fleet-protocol", "do-research", "components-and-combinators", "my-packages", "projreg")
FLEET_SEARCH_COMMAND = re.compile(
    r"(?:^|[;&(]|&&)\s*(?:ir|projreg|gh\s+search|priv\s+(?:find|where|show-dependents))(?:\s|$)"
)
#: A local search: Grep and Glob, or rg/grep/find/fd starting a Bash command. Agents do this
#: in nearly every session, so it is reported as context, not as the number.
LOCAL_SEARCH_TOOLS = ("Grep", "Glob")
LOCAL_SEARCH_COMMAND = re.compile(r"(?:^|[;&(]|&&)\s*(?:rg|grep|find|fd)(?:\s|$)")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
TRIGGERS = ("trigger-prompt", "trigger-fix-commit")
COMPONENT_TITLE = "Component:"

#: One transcript: ``(session_id, records)``.
Session = tuple[str, list]


# --- sources ----------------------------------------------------------------------------------


def transcripts(home: str | os.PathLike | None = None, *, days: float = DFLT_DAYS) -> Iterator[Session]:
    """Top-level Claude Code transcripts under ``home`` (default ``~/.claude``) modified within
    ``days``, as ``(session_id, records)``; a session found twice is read once."""
    base = Path(home or DFLT_CLAUDE_HOME).expanduser() / "projects"
    if not base.is_dir():
        return
    cutoff = datetime.now().timestamp() - days * 86400
    seen: set[str] = set()
    for path in sorted(base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.stat().st_mtime < cutoff or path.stem in seen:
            continue
        seen.add(path.stem)
        records = []
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    records.append(obj)
        yield path.stem, records


def tool_uses(records: Iterable[Mapping]) -> Iterator[tuple[str, str, Mapping]]:
    """``(cwd, tool name, input)`` for every tool call in a transcript, in order.

    >>> rec = {"type": "assistant", "cwd": "/w", "message": {"content": [
    ...     {"type": "tool_use", "name": "Grep", "input": {"pattern": "x"}}]}}
    >>> list(tool_uses([rec]))
    [('/w', 'Grep', {'pattern': 'x'})]
    """
    for r in records:
        if r.get("type") != "assistant":
            continue
        content = (r.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield str(r.get("cwd") or ""), str(block.get("name") or ""), block.get("input") or {}


def installed_skills(dirs: Iterable[str | os.PathLike]) -> list[str]:
    """Skill names: the folders holding a ``SKILL.md`` directly under each of ``dirs``."""
    names = set()
    for d in dirs:
        base = Path(d).expanduser()
        if base.is_dir():
            names.update(p.parent.name for p in base.glob("*/SKILL.md"))
    return sorted(names)


def gh_component_issues(*, since: str, title: str = COMPONENT_TITLE, limit: int = 500) -> int:
    """How many issues the ``gh`` user filed since ``since`` (a date) whose title has ``title``."""
    done = subprocess.run(
        ["gh", "search", "issues", f'"{title}" in:title', "--author", "@me", "--created", f">={since}",
         "--limit", str(limit), "--json", "title"],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    if done.returncode:
        raise RuntimeError(f"gh search failed: {(done.stderr or done.stdout).strip()[-300:]}")
    return sum(1 for i in json.loads(done.stdout or "[]") if title in str(i.get("title", "")))


def read_events(path: str | os.PathLike | None = None) -> list[dict]:
    """The fix-at-source hook's events (``$FIX_AT_SOURCE_LOG``, else its default path)."""
    p = Path(path or os.environ.get(EVENTS_ENVVAR) or DFLT_EVENTS).expanduser()
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


# --- the five numbers ---------------------------------------------------------------------------


def _ratio(k: int, n: int) -> float | None:
    return round(k / n, 3) if n else None


def _search_kind(name: str, args: Mapping) -> str | None:
    """``'fleet'``, ``'local'`` or ``None``.

    >>> _search_kind("Bash", {"command": "cd x && projreg find dol"}), _search_kind("Bash", {"command": "rg foo"})
    ('fleet', 'local')
    >>> _search_kind("Bash", {"command": "git log | grep x"}) is None
    True
    """
    if name in ("Agent", "Task"):
        return "fleet" if args.get("subagent_type") in SEARCH_AGENTS else None
    if name == "Skill":
        return "fleet" if str(args.get("skill", "")).split(":")[-1] in SEARCH_SKILLS else None
    if name in LOCAL_SEARCH_TOOLS:
        return "local"
    if name == "Bash":
        command = str(args.get("command", ""))
        if FLEET_SEARCH_COMMAND.search(command):
            return "fleet"
        if LOCAL_SEARCH_COMMAND.search(command):
            return "local"
    return None


def search_before_write(sessions: Iterable[Session], *, suffixes: tuple[str, ...] = SOURCE_SUFFIXES) -> dict:
    """Number 1: new source files written after a fleet search, over all new source files.

    ``local_first`` (after at least a Grep, a Glob or an ``rg``) is context.

    >>> def use(name, **args):
    ...     return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": args}]}}
    >>> s = [use("Write", file_path="/a.py"), use("Grep", pattern="x"), use("Write", file_path="/b.py"),
    ...      use("Bash", command="projreg find x"), use("Write", file_path="/c.py"), use("Write", file_path="/c.py")]
    >>> search_before_write([("s", s)])
    {'new_source_files': 3, 'searched_first': 1, 'ratio': 0.333, 'local_first': 2}
    """
    n = k = local = 0
    for _, records in sessions:
        fleet = near = False
        touched: set[str] = set()
        for _, name, args in tool_uses(records):
            kind = _search_kind(name, args)
            fleet = fleet or kind == "fleet"
            near = near or kind is not None
            path = str(args.get("file_path") or args.get("notebook_path") or "")
            if name == "Write" and path.endswith(suffixes) and path not in touched:
                n += 1
                k += fleet
                local += near
            if path and name in ("Read", *EDIT_TOOLS):
                touched.add(path)
    return {"new_source_files": n, "searched_first": k, "ratio": _ratio(k, n), "local_first": local}


def skill_use(sessions: Iterable[Session], *, installed: Iterable[str]) -> dict:
    """Number 2: invocations per skill, and the installed skills no session invoked."""
    counts: Counter = Counter()
    for _, records in sessions:
        for _, name, args in tool_uses(records):
            if name == "Skill" and args.get("skill"):
                counts[str(args["skill"]).split(":")[-1]] += 1
    installed = sorted(set(installed))
    never = [s for s in installed if not counts[s]]
    return {
        "installed": len(installed), "invoked": dict(counts.most_common()), "never_invoked": never,
        "never_share": _ratio(len(never), len(installed)),
    }  # fmt: skip


def _nearest_claude_md(path: str, *, is_file: Callable[[Path], bool], stop: Path) -> Path | None:
    for parent in Path(path).parents:
        if parent == stop or parent == parent.parent:
            return None
        if is_file(parent / "CLAUDE.md"):
            return parent
    return None


def claude_md_before_edit(
    sessions: Iterable[Session],
    *,
    is_file: Callable[[Path], bool] | None = None,
    stop: str | os.PathLike = "~",
) -> dict:
    """Number 3: (session, package) pairs whose nearest ``CLAUDE.md`` was loaded before the first edit.

    Loaded means the session's cwd is inside the package (Claude Code loads it), or the session
    read the file. ``stop`` is where the search for a ``CLAUDE.md`` ends (default: home).
    """
    stop = Path(stop).expanduser()
    is_file = is_file or Path.is_file
    roots: dict[str, Path | None] = {}
    n = k = 0
    for _, records in sessions:
        read, done = set(), set()
        for cwd, name, args in tool_uses(records):
            path = str(args.get("file_path") or args.get("notebook_path") or "")
            if not path:
                continue
            if name == "Read":
                read.add(PurePath(path).as_posix())
                continue
            if name not in EDIT_TOOLS:
                continue
            if path not in roots:
                roots[path] = _nearest_claude_md(path, is_file=is_file, stop=stop)
            root = roots[path]
            if root is None or root in done:
                continue
            done.add(root)
            n += 1
            inside = bool(cwd) and (Path(cwd) == root or root in Path(cwd).parents)
            k += inside or (root / "CLAUDE.md").as_posix() in read
    return {"packages_edited": n, "claude_md_first": k, "ratio": _ratio(k, n)}


def component_issues(*, days: float, now: datetime, search: Callable[..., int] = gh_component_issues) -> dict:
    """Number 4: ``Component:`` issues filed in the window, and per week."""
    since = (now - timedelta(days=days)).date().isoformat()
    filed = search(since=since)
    return {"filed": filed, "per_week": round(filed / (days / 7), 2)}


def corrections(events: Iterable[Mapping], *, days: float, now: datetime) -> dict:
    """Number 5: corrections written back (``writeback-seen``) over triggers, in the window."""
    since = (now - timedelta(days=days)).replace(tzinfo=None).isoformat(timespec="seconds")
    kinds = Counter(str(e.get("event")) for e in events if str(e.get("ts", "")) >= since)
    triggers = sum(kinds[t] for t in TRIGGERS)
    return {
        "triggers": triggers, "writebacks": kinds["writeback-seen"], "stop_blocks": kinds["stop-block"],
        "ratio": _ratio(min(kinds["writeback-seen"], triggers), triggers),
    }  # fmt: skip


# --- the look -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Number:
    """One of the five: where its value is in the result, which way is better, and the change it suggests."""

    key: str
    label: str
    field: str
    better: str  # 'higher' or 'lower'
    target: str  # one target condition, as a sentence with {value}


NUMBERS = (
    Number("search_before_write", "Search before write (new source files)", "ratio", "higher",
           "Raise the share of new source files written after a search from {value} (a rung-2 hook line at the first Write of a new source file, per setup-self-improvement section 1)."),
    Number("skill_use", "Skills never invoked", "never_share", "lower",
           "Cut the never-invoked skills from {value} of those installed: make the unused ones name-only or retire them, rather than lengthen their descriptions."),
    Number("claude_md_before_edit", "Package CLAUDE.md loaded before edit", "ratio", "higher",
           "Raise the share of edited packages whose CLAUDE.md was loaded first from {value} (a hook line naming the package's CLAUDE.md at the first edit outside the cwd)."),
    Number("component_issues", "Component issues per week", "per_week", "higher",
           "Component issues are at {value} a week: check that new ad hoc code is turned into a component issue (gap-to-issue) before the session ends."),
    Number("corrections", "Corrections written back", "ratio", "higher",
           "Raise the corrections written back from {value} of the triggers (fix-at-source: the Stop hook's reminder, or the skill's line in the always-loaded CLAUDE.md)."),
)  # fmt: skip


def _value(result: Mapping, number: Number):
    return (result.get(number.key) or {}).get(number.field)


def _previous(history: Path, today: str) -> dict | None:
    if not history.is_dir():
        return None
    earlier = sorted(p for p in history.glob("*.json") if p.stem < today)
    for p in reversed(earlier):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def propose(result: Mapping, previous: Mapping | None) -> dict:
    """One target condition: the number that got worse the most since last time; with no
    history, the weakest of the shares (a share's distance from its best value).

    >>> r = {"search_before_write": {"ratio": 0.9}, "corrections": {"ratio": 0.4}}
    >>> propose(r, None)["key"]
    'corrections'
    >>> propose(r, {"numbers": {"search_before_write": 1.0, "corrections": 0.4}})["key"]
    'search_before_write'
    """
    scored = []
    for num in NUMBERS:
        value = _value(result, num)
        if value is None:
            continue
        sign = 1 if num.better == "higher" else -1
        if previous:
            before = (previous.get("numbers") or {}).get(num.key)
            if before is None:
                continue
            worse = sign * (before - value)
            scale = max(abs(before), 1e-9) if num.field == "per_week" else 1.0
            scored.append((worse / scale, num, value))
        elif num.field != "per_week":
            scored.append(((1 - value) if sign > 0 else value, num, value))
    if not scored:
        return {"key": None, "text": "Nothing to compare yet: no number has a value."}
    score, num, value = max(scored, key=lambda t: t[0])
    if previous and score <= 0:
        return {"key": None, "text": "No number got worse since the last look: keep last week's change, or pick one yourself."}
    return {"key": num.key, "label": num.label, "value": value, "text": num.target.format(value=value)}


def weekly(
    *,
    days: float = DFLT_DAYS,
    home: str | None = None,
    sessions: Iterable[Session] | None = None,
    skills_dirs: Iterable[str | os.PathLike] | None = None,
    search: Callable[..., int] = gh_component_issues,
    events: Iterable[Mapping] | None = None,
    history: str | os.PathLike | None = None,
    save: bool = True,
    now: datetime | None = None,
) -> dict:
    """The five numbers over the last ``days``, last time's values, and one proposed change.

    Saves this run's numbers to ``history`` (``$OPSWARD_WEEKLY_DIR``, else
    ``~/.local/share/opsward/weekly``) as ``YYYY-MM-DD.json`` unless ``save=False``.
    """
    now = now or datetime.now(timezone.utc)
    claude_home = Path(home or DFLT_CLAUDE_HOME).expanduser()
    sessions = list(sessions if sessions is not None else transcripts(claude_home, days=days))
    skills_dirs = list(skills_dirs) if skills_dirs is not None else [claude_home / "skills"]
    result: dict = {
        "window_days": days,
        "at": now.isoformat(timespec="seconds"),
        "sessions": len(sessions),
        "search_before_write": search_before_write(sessions),
        "skill_use": skill_use(sessions, installed=installed_skills(skills_dirs)),
        "claude_md_before_edit": claude_md_before_edit(sessions),
        "corrections": corrections(read_events() if events is None else events, days=days, now=now),
    }
    try:
        result["component_issues"] = component_issues(days=days, now=now, search=search)
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as e:
        result["component_issues"] = {"error": str(e)[:300]}
    result["numbers"] = {num.key: _value(result, num) for num in NUMBERS}
    folder = Path(history or os.environ.get(HISTORY_ENVVAR) or DFLT_HISTORY).expanduser()
    today = now.date().isoformat()
    previous = _previous(folder, today)
    result["previous"] = {"at": previous.get("at"), "numbers": previous.get("numbers")} if previous else None
    result["proposal"] = propose(result, previous)
    if save:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{today}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def render(result: Mapping) -> str:
    """The weekly look as a markdown page: the numbers, the change since last time, one proposal."""
    prev = ((result.get("previous") or {}).get("numbers")) or {}
    lines = [f"# Weekly look: the setup's five numbers (last {result['window_days']:g} days, {result['sessions']} sessions)", ""]
    lines += ["| # | Number | Now | Last time | Better |", "|---|---|---|---|---|"]
    for i, num in enumerate(NUMBERS, 1):
        now_v = result["numbers"].get(num.key)
        shown = "n/a" if now_v is None else f"{now_v:g}"
        before = prev.get(num.key)
        lines.append(f"| {i} | {num.label} | {shown} | {'' if before is None else f'{before:g}'} | {num.better} |")
    skills = result["skill_use"]
    if skills["never_invoked"]:
        listed = ", ".join(skills["never_invoked"][:20])
        more = f" and {len(skills['never_invoked']) - 20} more" if len(skills["never_invoked"]) > 20 else ""
        lines += ["", f"Never invoked ({len(skills['never_invoked'])} of {skills['installed']}): {listed}{more}."]
    if "error" in result["component_issues"]:
        lines += ["", f"Component issues: not counted ({result['component_issues']['error']})."]
    c = result["corrections"]
    lines += ["", f"Corrections: {c['triggers']} triggers, {c['writebacks']} written back, {c['stop_blocks']} stop blocks."]
    lines += ["", "## One proposed target condition", "", result["proposal"]["text"], "",
              "The change is yours to pick: make one, at the highest rung of the mechanism ladder that fits, and measure it next week."]  # fmt: skip
    return "\n".join(lines) + "\n"
