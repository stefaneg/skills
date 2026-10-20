# skills

My agent skills, and the ones I borrow from other people, managed from one manifest.

Skills are installed for **Claude Code** (`~/.claude/skills`) and **Codex and friends**
(`~/.agents/skills`) from the same declaration, at user or project scope.

Requires Python 3.12+ and Git. The CLI uses the Python standard library; no packages
need installing. `bin/skills` is the entry point, with reconciliation in `lib/skill_manager.py`.

## The idea

One file — [`skills.json`](./skills.json) — selects user and project skills, their
sources, and tiers. Sources and revision pins are shared; each scope has its own
install list, targets, and receipts.

```json
{ "skill": "tdd",       "source": "mattpocock", "tier": "auto" }
{ "skill": "prototype", "source": "mattpocock", "tier": "on-demand" }
```

`bin/skills sync` reconciles user targets. `bin/skills sync --project axis` reconciles
only Axis. `--all` explicitly selects every registered scope. Sync resolves and
preflights the complete selection before copying, pruning, or writing pins.

Skills are **copied, not symlinked**. Existing symlinked target directories are
resolved, deduplicated, and written to directly. The installer preserves the aliases
and creates no links. Each physical target keeps a `.skills-receipt.json`; directories
without receipt entries are foreign and left alone.

## Tiers

The tier is the whole point of this repo. It separates *what is installed* from
*what the model is allowed to consider*.

| tier | on disk | in the model's skill listing | how you run it |
| --- | --- | --- | --- |
| `auto` | yes | yes | Claude picks it, or you type `/name` |
| `on-demand` | yes | **no** | you type `/name` |
| `off` | no | no | — |

`on-demand` maps to Claude Code's `skillOverrides: { "<skill>": "user-invocable-only" }`.
Settings are written only with `--write-settings`. The CLI currently enforces tiers
through Claude settings; it does not generate Codex invocation metadata, so Codex
does not receive the same visibility guarantee.

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
bin/skills sync --project axis     # only Axis's declared project additions
bin/skills sync --project axis --dry-run  # preview using cached sources; write nothing
bin/skills sync --all              # user and all registered projects
bin/skills list                    # manifest with resolved source paths
bin/skills status                  # installed copies, drift, and foreign skills
bin/skills update [source]         # preflight affected scopes, then advance shared pins
bin/skills overrides               # print the skillOverrides block without applying it
bin/skills doctor                  # unresolvable entries, duplicates, tier counts
```

`list`, `status`, `doctor`, and `overrides` also accept `--project NAME` and `--all`.
`update` changes shared pins, so accepts a source rather than a project selector.
Pinned sync works offline when the revision is cached; missing pins are fetched,
never silently replaced by the latest revision. A dry-run needs cached pins.

### Register a project

Add a `projects` object alongside the existing user `targets` and `install`:

```json
"projects": {
  "axis": {
    "root": "../axis",
    "install": [
      { "skill": "brainstorming", "source": "superpowers", "tier": "on-demand" }
    ]
  }
}
```

Project roots and local source paths resolve relative to this Skills repo, not the
shell's working directory. Each project targets `<root>/.claude/skills` and
`<root>/.agents/skills`. Axis is registered with an empty list initially; its existing
project-authored skills are foreign and are not adopted.

Project lists contain additional skills. User skills remain available through each
agent's discovery; project sync does not copy them again. Sync and doctor reject names
declared in both scopes or colliding with personal skill copies. Projects may use the
same names as other projects, provided their physical targets are separate.

If Axis's `.agents/skills` points to `.claude/skills`, sync writes once to the resolved
`.claude/skills` directory, with one receipt and pruning pass. Broken links, cycles,
and overlapping targets belonging to different scopes stop preflight.

`overrides --project axis` prints only Axis's Claude overrides. An explicit
`sync --project axis --write-settings` merges them into
`<root>/.claude/settings.local.json`, backing up that file and preserving unrelated
settings. The tool records its written keys under `.skills-work/settings`; removing
a managed override restores its previous value if nobody has changed the written
value since. Ignore `settings.local.json` in the project if needed; sync does not
edit project Git ignore rules. It never writes the team's `.claude/settings.json`.

To unregister a project, empty its install list and sync it first, resolving any
customised removals, then remove its registration. Deleting the registration alone
does not remove copies from an unselected directory.

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
Renames and deletions do: sync and update stop before changing copies or pins;
doctor reports them. Ambiguous names in a source also fail instead of picking one.

### Remove a skill

Delete the entry and sync its scope. Pruning touches only receipt-owned copies.
Customised project copies require an explicit choice before removal, including when
their tier becomes `off`. Project `off` does not disable a user-installed skill.

### Editing a skill

For user skills, edit the source and re-sync. User copies are generated and their
drift is overwritten; status calls it `edited`.

For project skills, edit the installed copy in the project. Status calls it
`customised`. Sync preserves it while the source content is unchanged, including
when only the tier or upstream commit changes. The receipt's `hash` covers every
relative filename and file's content in the source directory, not only `SKILL.md`;
`sourceRevision` records the Git commit, or `null` for local sources.

Each project target stores source snapshots beside the skill directory, under
`.claude/.skills-baselines/<hash>` or `.agents/.skills-baselines/<hash>` (after target
resolution). These are the common ancestors for future merges and sit outside skill
discovery. Keep snapshots with receipts; deleting
`vendor/` must not destroy the information needed to preserve project edits.

If both source and project content changed, sync stops before writing any selected
scope and offers:

```bash
bin/skills sync --project axis --merge brainstorming    # merge upstream into local edits
bin/skills sync --project axis --keep brainstorming     # skip; retain the old baseline
bin/skills sync --project axis --replace brainstorming  # explicitly discard local edits
```

A successful merge records the incoming source as the new baseline; the customised
copy can still differ from it. Clean additions and deletions merge too. Conflicts
leave installed copies unchanged and save a draft under `.skills-work/merges`.
Resolve that draft, then install it explicitly with
`--resolved 'brainstorming=/path/to/draft'`. Binary and add/delete conflicts retain
the local version in the draft and need manual resolution. A conflicting dry-run
does not save a draft. Draft metadata detects intervening changes to the baseline,
project copy, or incoming content; a stale draft is rejected. `--keep` on removal leaves the old copy and its receipt managed;
future syncs ask again until the removal is resolved.

`update` fetches candidate revisions and checks affected scopes before writing the
shared lockfile. It installs nothing. It accepts the same choices, for example
`bin/skills update superpowers --merge brainstorming`. After advancing a pin, sync
the desired project and repeat the choice; a clean merge during update is a check,
not an installation. Choices apply by skill name across selected targets.

Older receipts remain readable. If a legacy project baseline cannot be recovered
from its recorded hash/revision, sync still offers keep or replace, but cannot merge.
Symlinks within a skill directory are unsupported; target-directory aliases are
supported. Hashes cover contents and paths, not permissions or empty directories.

## Layout

```
skills/            skills I wrote or adopted — the only place with real content
skills.json        the manifest: sources, installs, tiers
skills.lock.json   resolved commit SHA per external source (generated, committed)
vendor/            shallow clones of external repos (generated, gitignored)
bin/skills         the CLI
lib/               source resolution, planning, reconciliation, and merging
tests/             isolated CLI integration tests
docs/adr/          why this is built the way it is
```

## Versioning

`skills.lock.json` pins each external source to a commit. `sync` respects the pin;
`update` is the only command that moves it. Upstream skill repos change under you —
Matt has deleted and renamed several skills since I first installed them — so an
explicit update step is the difference between "my setup changed" and "my setup
changed and I know why".

Run `python3 -m unittest discover -s tests -v` to verify changes. Tests copy the repo,
rewrite the manifest, and use temporary user/project targets and local Git remotes.
They never sync live installations.

Skills that upstream deletes but I still want get copied into `skills/` and switched to
`source: "own"`. Once I fork a skill, I own it.
