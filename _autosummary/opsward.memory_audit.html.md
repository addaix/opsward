# opsward.memory_audit

Memory audit: fleet-wide rules stranded in project-local auto-memory, and who should own them.

Claude Code’s auto-memory is keyed by working directory: a `feedback` memory written in one
project loads only in sessions started there. A rule that holds for every project is stranded
in that one. This audit lists every memory of the chosen kinds, then for each one:

- **scope**: `project` or `fleet`, with the reason ([`classify()`](#opsward.memory_audit.classify), a heuristic; pass
  `classify=` to use a judge instead);
- **duplicates**: memories in *other* directories that say nearly the same thing
  ([`similarity()`](#opsward.memory_audit.similarity), lexical, replaceable);
- **owner**: for a fleet-wide one, the installed skill whose name and description match it
  best, else `~/.claude/CLAUDE.md`, and whether the owner already says it;
- **stub**: a memory that only says it moved elsewhere, listed for deletion.

Report-only: it never writes, moves or deletes a memory. The user curates the table.

```pycon
>>> parse_frontmatter("---\nname: x\nmetadata:\n  type: feedback\n---\nbody")
({'name': 'x', 'type': 'feedback'}, 'body')
```

### Module Attributes

| [`DUPLICATE_AT`](#opsward.memory_audit.DUPLICATE_AT)   | Two memories in different directories at or above this similarity are reported as duplicates.                               |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| [`OWNER_AT`](#opsward.memory_audit.OWNER_AT)       | A skill must match a fleet-wide memory at least this well to be proposed as its owner.                                      |
| [`COVERED_AT`](#opsward.memory_audit.COVERED_AT)     | Share of a memory's distinctive words its owner must already hold to say "already there".                                   |
| [`FLEET_CUES`](#opsward.memory_audit.FLEET_CUES)     | Words that mark a rule as a habit for every project.                                                                        |
| [`CWD_SCAN_LINES`](#opsward.memory_audit.CWD_SCAN_LINES) | How many lines of each transcript [`project_dir()`](#opsward.memory_audit.project_dir) reads looking for a `cwd`. |

### Functions

| [`audit`](#opsward.memory_audit.audit)(\*[, home, kinds, found, skills_dirs, ...])   | Audit the memories (`found`, default: [`memories()`](#opsward.memory_audit.memories) of `home` and `kinds`).                                  |
|------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`classify`](#opsward.memory_audit.classify)(memory)                                    | `(scope, reason)`: `project` when the memory names its own project (and is not phrased as a habit), else `fleet` or `project` by its wording.              |
| [`is_stub`](#opsward.memory_audit.is_stub)(memory, \*[, short, head])                  | A memory that says it moved: the marker in its name or opening, or anywhere in a short one.                                                                |
| [`memories`](#opsward.memory_audit.memories)([home, kinds])                             | Every memory of `kinds` under `home`'s project folders (`MEMORY.md` indexes excluded).                                                                     |
| [`names_project`](#opsward.memory_audit.names_project)(text, name)                           | Whether `text` names the project `name`, with `-`, `_` and space equivalent and no letter or digit on either side.                                         |
| [`parse_frontmatter`](#opsward.memory_audit.parse_frontmatter)(text)                             | `(fields, body)`: flat `key: value` fields of a `---` block, nested `metadata` keys lifted to the top (`metadata: type: feedback` gives `type`).           |
| [`project_dir`](#opsward.memory_audit.project_dir)(folder, \*[, scan_lines])               | The working directory a project folder is for, read from its transcripts, else `""`.                                                                       |
| [`project_name`](#opsward.memory_audit.project_name)(slug[, cwd])                           | The project a directory names: the last part of its real `cwd` when known, else the last part of the slug (lossy: `tw_platform` comes back as `platform`). |
| [`project_slug`](#opsward.memory_audit.project_slug)(path)                                  | Claude Code's folder name for a working directory: every non-alphanumeric is `-`.                                                                          |
| [`render`](#opsward.memory_audit.render)(result, \*[, home])                          | The audit as a markdown page: fleet-wide memories and their proposed owner first.                                                                          |
| [`similarity`](#opsward.memory_audit.similarity)(a, b)                                    | Jaccard similarity of two texts' distinctive words.                                                                                                        |
| [`skills`](#opsward.memory_audit.skills)(dirs)                                        | `{name: "name description"}` of the skills under `dirs` (`*/SKILL.md`).                                                                                    |
| [`words`](#opsward.memory_audit.words)(text)                                         | The distinctive words of `text`: lowercase, three letters or more, no stopwords.                                                                           |

### Classes

| [`Memory`](#opsward.memory_audit.Memory)(path, project, kind, name, ...[, ...])   | One memory file.   |
|--------------------------------------------------------------------------------------------------|--------------------|

### opsward.memory_audit.COVERED_AT *= 0.6*

Share of a memory’s distinctive words its owner must already hold to say “already there”.

### opsward.memory_audit.CWD_SCAN_LINES *= 200*

How many lines of each transcript [`project_dir()`](#opsward.memory_audit.project_dir) reads looking for a `cwd`.

### opsward.memory_audit.DUPLICATE_AT *= 0.45*

Two memories in different directories at or above this similarity are reported as duplicates.

### opsward.memory_audit.FLEET_CUES *= re.compile('\\\\b(always|never|every (?:project|repo|package|session)|in general|whenever|by default|from now on|across (?:the )?(?:fleet|projects|repos))\\\\b', re.IGNORECASE)*

Words that mark a rule as a habit for every project.

### *class* opsward.memory_audit.Memory(path, project, kind, name, description, body, modified, project_dir='', scope='', reason='', duplicates=list(), owner='', owner_score=0.0, covered=False, stub=False)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One memory file.

### opsward.memory_audit.OWNER_AT *= 0.08*

A skill must match a fleet-wide memory at least this well to be proposed as its owner.

### opsward.memory_audit.audit(\*, home=None, kinds=('feedback', ), found=None, skills_dirs=None, global_claude_md=None, read_owner=None, classify=<function classify>, similarity=<function similarity>, duplicate_at=0.45, owner_at=0.08)

Audit the memories (`found`, default: [`memories()`](#opsward.memory_audit.memories) of `home` and `kinds`).

`read_owner(owner)` returns an owner’s text, to say whether it already holds the rule
(default: the skill’s `SKILL.md`, or the global `CLAUDE.md`).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### opsward.memory_audit.classify(memory)

`(scope, reason)`: `project` when the memory names its own project (and is not
phrased as a habit), else `fleet` or `project` by its wording.

```pycon
>>> m = Memory("p", "-x-t-priv", "feedback", "n", "", "Always route LLM calls through aix.", "")
>>> classify(m)
('fleet', "worded as a habit ('Always') and does not name priv")
>>> classify(Memory("p", "-x-t-priv", "feedback", "n", "", "In priv, the CLI golden must be re-recorded.", ""))
('project', 'names its own project (priv)')
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### opsward.memory_audit.is_stub(memory, , short=400, head=200)

A memory that says it moved: the marker in its name or opening, or anywhere in a short one.

```pycon
>>> is_stub(Memory("p", "x", "feedback", "old-rule-SUPERSEDED", "", "x " * 400, ""))
True
>>> is_stub(Memory("p", "x", "feedback", "rule", "", "Prefer dol. " * 50 + "It replaced by hand.", ""))
False
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### opsward.memory_audit.memories(home=None, , kinds=('feedback',))

Every memory of `kinds` under `home`’s project folders (`MEMORY.md` indexes excluded).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Memory`](#opsward.memory_audit.Memory)]

### opsward.memory_audit.names_project(text, name)

Whether `text` names the project `name`, with `-`, `_` and space equivalent
and no letter or digit on either side.

```pycon
>>> names_project("Deploys of tw-platform go through deploy.py.", "tw_platform")
True
>>> names_project("In tw_platform, never rsync.", "platform")
True
>>> names_project("the iq_platformer tool", "iq_platform")
False
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### opsward.memory_audit.parse_frontmatter(text)

`(fields, body)`: flat `key: value` fields of a `---` block, nested `metadata`
keys lifted to the top (`metadata: type: feedback` gives `type`).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### opsward.memory_audit.project_dir(folder, , scan_lines=200)

The working directory a project folder is for, read from its transcripts, else `""`.

The folder’s name is a lossy slug (`tw_platform` and `tw-platform` both give
`tw-platform`), but each transcript records the real `cwd`. The first one whose
slug is the folder’s name wins, newest transcript first.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### opsward.memory_audit.project_name(slug, cwd='')

The project a directory names: the last part of its real `cwd` when known, else
the last part of the slug (lossy: `tw_platform` comes back as `platform`).

```pycon
>>> project_name("-Users-me-Dropbox-py-proj-t-priv")
'priv'
>>> project_name("-Users-me-proj-tt-tw-platform", "/Users/me/proj/tt/tw_platform")
'tw_platform'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### opsward.memory_audit.project_slug(path)

Claude Code’s folder name for a working directory: every non-alphanumeric is `-`.

```pycon
>>> project_slug("/Users/me/proj/tt/tw_platform")
'-Users-me-proj-tt-tw-platform'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### opsward.memory_audit.render(result, , home=None)

The audit as a markdown page: fleet-wide memories and their proposed owner first.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### opsward.memory_audit.similarity(a, b)

Jaccard similarity of two texts’ distinctive words.

```pycon
>>> similarity("prefer the storage facade dol", "the dol storage facade, always")
1.0
>>> similarity("route calls through aix", "route storage through dol")
0.333
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### opsward.memory_audit.skills(dirs)

`{name: "name description"}` of the skills under `dirs` (`*/SKILL.md`).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### opsward.memory_audit.words(text)

The distinctive words of `text`: lowercase, three letters or more, no stopwords.

```pycon
>>> sorted(words("Always route LLM calls through aix, never directly."))
['aix', 'calls', 'directly', 'llm', 'route', 'through']
```

* **Return type:**
  [`set`](https://docs.python.org/3/builtins/stdtypes.html#set)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
