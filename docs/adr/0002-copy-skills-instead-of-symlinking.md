# ADR 0002 — Copy skills into targets instead of symlinking

**Status**: accepted — supersedes the symlink decision in [ADR 0001](./0001-manifest-driven-skill-management.md)
**Date**: 2026-08-04

## Context

ADR 0001 installed skills by symlinking each one from `skills/` or `vendor/` into
`~/.claude/skills` and `~/.agents/skills`. That gave a nice property: editing a skill in
the repo took effect immediately, with no install step.

It also broke sandboxed sessions. A sandboxed agent can only see paths inside the
sandbox, and a symlink pointing at `~/src/github.com/stefaneg/skills/skills/tdd` resolves
outside it. The skill appears in the listing and then fails to load.

Running unsandboxed to keep symlinks working is the wrong trade — the sandbox is a
security boundary, the symlink is a convenience.

## Decision

`sync` copies each skill's directory into every target.

This costs the property that made pruning safe. A symlink pointing into the repo was
self-evidently ours; a copied directory is indistinguishable from one placed there by
`npx skills`, a plugin, or by hand. Deleting on the basis of "not in the manifest" would
mean deleting other tools' work.

So each target carries a **receipt** — `.skills-receipt.json`, mapping skill name to
source, tier, and a content hash over relative paths. The receipt is the authority:

- `sync` overwrites or deletes a directory only if the receipt names it.
- Anything else in the target is *foreign* and never touched.
- A hash mismatch means someone edited the installed copy; `status` reports it as
  *edited* before `sync` overwrites it.

## Consequences

Good:

- Sandboxed sessions can read every installed skill.
- Foreign skills coexist safely, so this can be adopted incrementally.
- The receipt makes each target self-describing — it says what it holds and where each
  piece came from, without consulting the repo.

Bad, and accepted:

- Editing a skill now requires `bin/skills sync` to take effect. Easy to forget while
  iterating on a skill in `skills/`.
- An edit made directly to an installed copy is lost on the next sync. `status` surfaces
  it; nothing prevents it.
- The receipt can disagree with reality if a target is edited outside the tool. Recovery
  is `rm -rf` the target and re-sync, which is cheap because targets are derived state.
- Content hashing on every sync costs a `shasum` pass per skill. Negligible at this size.
