# skills

My agent skills, and the ones I borrow from other people, managed from one manifest.

Skills are installed for **Claude Code** (`~/.claude/skills`) and **Codex and friends**
(`~/.agents/skills`) at the same time, from the same declaration.

## The idea

One file — [`skills.json`](./skills.json) — says which skills exist on this machine,
where each one comes from, and how visible it is. Nothing else installs skills.

```json
{ "skill": "tdd",       "source": "mattpocock", "tier": "auto" }
{ "skill": "prototype", "source": "mattpocock", "tier": "on-demand" }
```

`bin/skills sync` makes the machine match the manifest: clones the sources it needs,
copies the skills into both targets, removes skills you deleted from the manifest, and
computes the `skillOverrides` block that enforces the tiers.

Skills are **copied, not symlinked** — sandboxed agent sessions can't follow a symlink
out of the sandbox. Each target keeps a `.skills-receipt.json` recording what was
installed and its content hash. That receipt is the only thing authorising `sync` to
delete or overwrite anything, so a directory you put there yourself is never touched.

## Tiers

The tier is the whole point of this repo. It separates *what is installed* from
*what the model is allowed to consider*.

| tier | on disk | in the model's skill listing | how you run it |
| --- | --- | --- | --- |
| `auto` | yes | yes | Claude picks it, or you type `/name` |
| `on-demand` | yes | **no** | you type `/name` |
| `off` | no | no | — |

`on-demand` maps to Claude Code's `skillOverrides: { "<skill>": "user-invocable-only" }`.

Skills are cheap in tokens — only name and description load at startup — but expensive
in *attention*: every extra description competes with every other one, and a model
choosing between 60 skills chooses worse than one choosing between 12. So the rule here
is **install broadly, expose narrowly**. Anything you would not want fired automatically
goes `on-demand` — it stays one keystroke away without ever entering the model's
decision.

Keep `auto` under about fifteen entries. If something in `auto` hasn't fired on its own
in a month, it belongs in `on-demand`.

## Usage

```bash
bin/skills sync                    # make the machine match the manifest
bin/skills sync --write-settings   # ...and apply skillOverrides to ~/.claude/settings.json
bin/skills list                    # manifest with resolved source paths
bin/skills status                  # what's linked, what's orphaned, what's foreign
bin/skills update [source]         # move a source to the tip of its ref, relock
bin/skills overrides               # print the skillOverrides block without applying it
bin/skills doctor                  # unresolvable entries, duplicates, tier counts
```

### Add a skill from a new repo

```jsonc
// 1. declare the source
"superpowers": { "type": "github", "repo": "obra/superpowers", "ref": "main" }

// 2. install what you want from it — start on-demand, promote if it earns it
{ "skill": "brainstorming", "source": "superpowers", "tier": "on-demand" }
```

```bash
bin/skills sync
```

Skills are located by directory name anywhere under the source, so upstream
reorganisations (`skills/engineering/tdd/` → `skills/core/tdd/`) don't break anything.
Renames and deletions do, loudly — `sync` warns and `doctor` lists them.

### Remove a skill

Delete the line, run `bin/skills sync`. The copy is removed. Pruning only ever touches
skills listed in that target's receipt, so anything installed by another tool survives.

### Editing a skill

Edit it in `skills/` and re-sync. **Never edit the copy in a target** — the next sync
overwrites it. `bin/skills status` flags copies that have drifted (`edited`) so a lost
change is at least a visible one.

## Layout

```
skills/            skills I wrote or adopted — the only place with real content
skills.json        the manifest: sources, installs, tiers
skills.lock.json   resolved commit SHA per external source (generated, committed)
vendor/            shallow clones of external repos (generated, gitignored)
bin/skills         the CLI
docs/adr/          why this is built the way it is
```

## Versioning

`skills.lock.json` pins each external source to a commit. `sync` respects the pin;
`update` is the only command that moves it. Upstream skill repos change under you —
Matt has deleted and renamed several skills since I first installed them — so an
explicit update step is the difference between "my setup changed" and "my setup
changed and I know why".

Skills that upstream deletes but I still want get copied into `skills/` and switched to
`source: "own"`. Once I fork a skill, I own it.
