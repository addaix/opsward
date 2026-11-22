# opsward.weekly

The weekly look: the agent setup’s five numbers, against last week, and one proposed change.

The `setup-self-improvement` loop asks for one improvement a week, chosen from five numbers
and passed through a human gate. This module prints the numbers; the user picks the change.
It only reads, and the only thing it writes is its own history (one JSON file per run).

The five numbers, over the last `days` (30 by default):

1. **Search before write**: of the new source files an agent wrote, the share written after
   the session had searched what the fleet already has (an Explore agent, a search skill
   such as `fleet-protocol`, or `ir`/`projreg`/`priv find`/`gh search` in Bash).
   Local greps are counted beside it as context: agents run them in nearly every session.
   A file counts as new when the session writes it without having read or edited it first.
2. **Skills never invoked**: the share of installed skills no session invoked (with the
   invocation count per skill). Never-invoked skills are candidates for name-only or
   deletion, not for a longer description.
3. **CLAUDE.md before edit**: of the packages a session edited, the share whose nearest
   `CLAUDE.md` the session had loaded first (its cwd is inside the package, or it read the
   file before the first edit).
4. **Component issues per week**: issues titled `Component: ...` the owner filed.
5. **Corrections written back**: `writeback-seen` events over the triggers (`trigger-prompt`,
   `trigger-fix-commit`) in the fix-at-source hook’s event log.

Only metadata is read: tool names, file paths, skill names, timestamps. Never prompt or file
text. Every source is a keyword argument (`sessions`, `skills_dirs`, `search`,
`events`, `history`), so a caller or a test can point it elsewhere.

```pycon
>>> NUMBERS[0].key, NUMBERS[1].better
('search_before_write', 'lower')
```

### Module Attributes

| [`SEARCH_AGENTS`](#opsward.weekly.SEARCH_AGENTS)      | an Explore agent, a search skill, or a fleet search command at the start of a Bash command (not after a pipe).   |
|---------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| [`LOCAL_SEARCH_TOOLS`](#opsward.weekly.LOCAL_SEARCH_TOOLS) | Grep and Glob, or rg/grep/find/fd starting a Bash command.                                                       |
| [`Session`](#opsward.weekly.Session)            | `(session_id, records)`.                                                                                         |

### Functions

| [`claude_md_before_edit`](#opsward.weekly.claude_md_before_edit)(sessions, \*[, ...])     | Number 3: (session, package) pairs whose nearest `CLAUDE.md` was loaded before the first edit.                                                                 |
|-------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`component_issues`](#opsward.weekly.component_issues)(\*, days, now[, search])      | Number 4: `Component:` issues filed in the window, and per week.                                                                                               |
| [`corrections`](#opsward.weekly.corrections)(events, \*, days, now)             | Number 5: corrections written back (`writeback-seen`) over triggers, in the window.                                                                            |
| [`gh_component_issues`](#opsward.weekly.gh_component_issues)(\*, since[, title, limit]) | How many issues the `gh` user filed since `since` (a date) whose title has `title`.                                                                            |
| [`installed_skills`](#opsward.weekly.installed_skills)(dirs)                         | Skill names: the folders holding a `SKILL.md` directly under each of `dirs`.                                                                                   |
| [`propose`](#opsward.weekly.propose)(result, previous)                      | One target condition: the number that got worse the most since last time; with no history, the weakest of the shares (a share's distance from its best value). |
| [`read_events`](#opsward.weekly.read_events)([path])                            | The fix-at-source hook's events (`$FIX_AT_SOURCE_LOG`, else its default path).                                                                                 |
| [`render`](#opsward.weekly.render)(result)                                 | The weekly look as a markdown page: the numbers, the change since last time, one proposal.                                                                     |
| [`search_before_write`](#opsward.weekly.search_before_write)(sessions, \*[, suffixes])  | Number 1: new source files written after a fleet search, over all new source files.                                                                            |
| [`skill_use`](#opsward.weekly.skill_use)(sessions, \*, installed)             | Number 2: invocations per skill, and the installed skills no session invoked.                                                                                  |
| [`tool_uses`](#opsward.weekly.tool_uses)(records)                             | `(cwd, tool name, input)` for every tool call in a transcript, in order.                                                                                       |
| [`transcripts`](#opsward.weekly.transcripts)([home, days])                      | Top-level Claude Code transcripts under `home` (default `~/.claude`) modified within `days`, as `(session_id, records)`; a session found twice is read once.   |
| [`weekly`](#opsward.weekly.weekly)(\*[, days, home, sessions, ...])        | The five numbers over the last `days`, last time's values, and one proposed change.                                                                            |

### Classes

| [`Number`](#opsward.weekly.Number)(key, label, field, better, target)   | One of the five: where its value is in the result, which way is better, and the change it suggests.   |
|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|

### opsward.weekly.LOCAL_SEARCH_TOOLS *= ('Grep', 'Glob')*

Grep and Glob, or rg/grep/find/fd starting a Bash command. Agents do this
in nearly every session, so it is reported as context, not as the number.

* **Type:**
  A local search

### *class* opsward.weekly.Number(key, label, field, better, target)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One of the five: where its value is in the result, which way is better, and the change it suggests.

### opsward.weekly.SEARCH_AGENTS *= ('Explore',)*

an Explore agent, a
search skill, or a fleet search command at the start of a Bash command (not after a pipe).

* **Type:**
  A search of what the fleet already has (the fleet-protocol meaning)

### opsward.weekly.Session

`(session_id, records)`.

* **Type:**
  One transcript

alias of [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]

### opsward.weekly.claude_md_before_edit(sessions, , is_file=None, stop='~')

Number 3: (session, package) pairs whose nearest `CLAUDE.md` was loaded before the first edit.

Loaded means the session’s cwd is inside the package (Claude Code loads it), or the session
read the file. `stop` is where the search for a `CLAUDE.md` ends (default: home).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.weekly.component_issues(\*, days, now, search=<function gh_component_issues>)

Number 4: `Component:` issues filed in the window, and per week.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.weekly.corrections(events, , days, now)

Number 5: corrections written back (`writeback-seen`) over triggers, in the window.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.weekly.gh_component_issues(, since, title='Component:', limit=500)

How many issues the `gh` user filed since `since` (a date) whose title has `title`.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### opsward.weekly.installed_skills(dirs)

Skill names: the folders holding a `SKILL.md` directly under each of `dirs`.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### opsward.weekly.propose(result, previous)

One target condition: the number that got worse the most since last time; with no
history, the weakest of the shares (a share’s distance from its best value).

```pycon
>>> r = {"search_before_write": {"ratio": 0.9}, "corrections": {"ratio": 0.4}}
>>> propose(r, None)["key"]
'corrections'
>>> propose(r, {"numbers": {"search_before_write": 1.0, "corrections": 0.4}})["key"]
'search_before_write'
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.weekly.read_events(path=None)

The fix-at-source hook’s events (`$FIX_AT_SOURCE_LOG`, else its default path).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### opsward.weekly.render(result)

The weekly look as a markdown page: the numbers, the change since last time, one proposal.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### opsward.weekly.search_before_write(sessions, , suffixes=('.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.rs', '.swift', '.go', '.kt', '.java', '.rb', '.sh', '.c', '.cc', '.cpp', '.h'))

Number 1: new source files written after a fleet search, over all new source files.

`local_first` (after at least a Grep, a Glob or an `rg`) is context.

```pycon
>>> def use(name, **args):
...     return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": args}]}}
>>> s = [use("Write", file_path="/a.py"), use("Grep", pattern="x"), use("Write", file_path="/b.py"),
...      use("Bash", command="projreg find x"), use("Write", file_path="/c.py"), use("Write", file_path="/c.py")]
>>> search_before_write([("s", s)])
{'new_source_files': 3, 'searched_first': 1, 'ratio': 0.333, 'local_first': 2}
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.weekly.skill_use(sessions, , installed)

Number 2: invocations per skill, and the installed skills no session invoked.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.weekly.tool_uses(records)

`(cwd, tool name, input)` for every tool call in a transcript, in order.

```pycon
>>> rec = {"type": "assistant", "cwd": "/w", "message": {"content": [
...     {"type": "tool_use", "name": "Grep", "input": {"pattern": "x"}}]}}
>>> list(tool_uses([rec]))
[('/w', 'Grep', {'pattern': 'x'})]
```

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)]]

### opsward.weekly.transcripts(home=None, , days=30)

Top-level Claude Code transcripts under `home` (default `~/.claude`) modified within
`days`, as `(session_id, records)`; a session found twice is read once.

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]

### opsward.weekly.weekly(\*, days=30, home=None, sessions=None, skills_dirs=None, search=<function gh_component_issues>, events=None, history=None, save=True, now=None)

The five numbers over the last `days`, last time’s values, and one proposed change.

Saves this run’s numbers to `history` (`$OPSWARD_WEEKLY_DIR`, else
`~/.local/share/opsward/weekly`) as `YYYY-MM-DD.json` unless `save=False`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
