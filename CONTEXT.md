# Context

Shared language for this repo. Read this before changing anything.

## Terms

**Skill** — a directory containing `SKILL.md` with `name` and `description` frontmatter.
The unit of installation. Never a file on its own.

**Source** — a place skills come from. Either `local` (this repo's `skills/`) or
`github` (an external repo, cached under `vendor/`). Sources are declared once and
referenced by name.

**Install entry** — one line in `skills.json` binding a skill name to a source and a
tier. The manifest's `install` array *is* the set of skills on this machine.

**Tier** — how visible a skill is to the model. `auto` (in the model's listing),
`on-demand` (installed, slash-invocable, invisible to the model), `off` (not installed).
Tiers are about attention, not about tokens.

**Target** — a directory a skill gets linked into. Two of them: `~/.claude/skills` for
Claude Code, `~/.agents/skills` for Codex and other agents that read the shared
convention.

**Receipt** — `.skills-receipt.json` at the root of each target, mapping installed skill
name to source, tier, and content hash. It is the record of what this tool put there.
`sync` may delete or overwrite a directory only if the receipt names it; everything else
in the target is **foreign** and left alone.

**Drift** — a copy in a target whose hash no longer matches its receipt entry. Means
someone edited the installed copy rather than the source. `status` reports it; `sync`
silently overwrites it.

**Rescued skill** — a skill an upstream repo deleted that we still want. Copied into
`skills/` and reassigned `source: "own"`. Rescuing is a one-way door.

## Boundaries

- The manifest is authoritative. Targets are derived state — a target can be deleted
  entirely and rebuilt by `sync`.
- **Install by copy, never by symlink.** Sandboxed agent sessions cannot follow a
  symlink out of the sandbox, so a linked skill is an invisible skill.
- A target is never edited by hand. Edit `skills/`, then sync.
- `vendor/` is a cache. Deleting it must never lose information; everything needed to
  rebuild it is in `skills.json` + `skills.lock.json`.
- We never edit anything under `vendor/`. To change an external skill, rescue it first.
- `sync` is idempotent and safe to run repeatedly. It is the only command that writes to
  targets.
- Writing to `~/.claude/settings.json` is opt-in (`--write-settings`) and always backs
  up first. Mutating global config silently is not acceptable.

## Two mechanisms for the same effect

A skill can be hidden from the model in two ways:

1. `disable-model-invocation: true` in its own frontmatter — available only for skills
   we control, and travels with the skill.
2. `skillOverrides: { "<skill>": "user-invocable-only" }` in Claude settings — works for
   any skill including vendored ones, and is Claude-specific.

This repo uses (2) uniformly, generated from tiers, so that one column in the manifest
explains the behaviour of every skill regardless of who wrote it. Don't mix in (1) for
own skills — it splits the source of truth.
