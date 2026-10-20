# Context

Shared language for this repo. Read this before changing anything.

## Terms

**Skill** — a directory containing `SKILL.md` with `name` and `description` frontmatter.
The unit of installation. Never a file on its own.

**Source** — a place skills come from. Either `local` (this repo's `skills/`) or
`github` (an external repo, cached under `vendor/`). Sources are declared once and
referenced by name.

**Install entry** — one line in `skills.json` binding a skill name to a source and a
tier within a scope. The top-level `install` array selects user skills; each
`projects.<name>.install` array selects that project's additional skills.

**Scope** — an independently reconciled user installation or named project. Sources
and their version pins are shared; install lists, target receipts, and settings are separate.

**Tier** — how visible a skill is to the model. `auto` (in the model's listing),
`on-demand` (installed, slash-invocable, invisible to the model), `off` (not installed).
Tiers are about attention, not about tokens.

**Target** — a directory skills are copied into. User targets are declared explicitly.
Project targets are `.claude/skills` and `.agents/skills` under the project's root.
Existing symlink aliases resolve to one physical target, with one receipt and pruning pass.

**Receipt** — `.skills-receipt.json` at the root of each target, mapping installed skill
name to source, tier, source revision, and baseline content hash. It records what this tool installed.
`sync` may delete or overwrite a directory only if the receipt names it; everything else
in the target is **foreign** and left alone.

**Baseline** — source content when a skill was last installed or merged. Project targets
retain that content beside the discovery directory, under `.skills-baselines/<hash>`,
so future merges have their common ancestor without exposing snapshots as skills.
The receipt's `hash` is the source baseline hash, not the hash of a merged project copy.

**Drift** — a user copy whose hash differs from its receipt. `status` reports it as
`edited`; sync restores the declared source.

**Customisation** — a project copy differing from its source baseline. Sync preserves it
while the source is unchanged. An upstream change, source switch, or removal stops preflight
until the user chooses to merge, keep the old version, or replace it.

**Rescued skill** — a skill an upstream repo deleted that we still want. Copied into
`skills/` and reassigned `source: "own"`. Rescuing is a one-way door.

## Boundaries

- The manifest is authoritative for selection. User targets are derived state.
  Project targets also contain customisations and baseline snapshots; preserve both.
- **Install by copy, never by symlink.** Sandboxed agent sessions cannot follow a
  symlink out of the sandbox, so a linked skill is an invisible skill.
- Edit user skills at their source. Customise project copies in the project; merge
  upstream changes explicitly when sync reports a conflict.
- `vendor/` is a cache. Deleting it must never lose information; everything needed to
  rebuild it is in `skills.json` + `skills.lock.json`.
- We never edit anything under `vendor/`. To change an external skill, rescue it first.
- `sync` is idempotent and safe to run repeatedly. It is the only command that writes to
  targets.
- Preflight checks every selected scope before writing installed copies or pins.
  `update` checks affected project copies before changing shared pins; it installs nothing.
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
