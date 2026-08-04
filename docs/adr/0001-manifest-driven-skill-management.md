# ADR 0001 — A manifest owns skill installation and visibility

**Status**: accepted
**Date**: 2026-08-04

## Context

Skills arrive from several places: ones I write, Matt Pocock's repo, Superpowers,
Vercel's. I want to try skills from a new repo without ceremony, and I want the number
of skills the model actively considers to stay small.

The previous setup was a fork of `mattpocock/skills` with a `link-skills.sh` that
symlinked *every* `SKILL.md` in the tree into both agent directories. Three problems:

1. All-or-nothing. Taking one skill from a repo meant carrying its whole tree, or
   maintaining a fork whose diff against upstream was "the files I deleted".
2. My own skills were entangled with someone else's git history, on a branch of their
   repo, which made both updating from upstream and sharing my own work awkward.
3. No way to install a skill without exposing it. `npx skills` and plugin marketplaces
   both install-and-expose as one act.

Meanwhile Claude Code grew the mechanism the setup was missing: `skillOverrides` with a
`user-invocable-only` state — a skill that stays runnable as `/name` but is dropped
from the listing the model sees.

## Decision

A single manifest (`skills.json`) declares sources, install entries, and a **tier** per
entry. `bin/skills sync` reconciles the machine to it and generates the `skillOverrides`
block from the tiers.

Corollaries:

- **Vendor, don't fork.** External repos are cloned into a gitignored `vendor/` and
  pinned by SHA in `skills.lock.json`. No fork to rebase, no deletions to maintain.
- **Cherry-pick by name.** An install entry names a skill; the resolver finds it by
  directory name anywhere under the source. Category reshuffles upstream are free.
- **Install ≠ expose.** Adding a skill costs nothing at the prompt unless its tier says
  `auto`. This is what makes objectives 2 and 3 stop fighting.
- **Own skills live here.** `skills/` is the only directory in the repo with real
  content, in my own history, shareable on its own.

## Consequences

Good:

- Adding a repo is two JSON lines. Trying ten skills from Superpowers costs zero
  attention if they go in `on-demand`.
- The manifest is a reviewable diff of my agent setup over time.
- Both agents stay in sync by construction, since targets are a list.

Bad, and accepted:

- I own a small bash CLI instead of using `npx skills`, which does provenance,
  lockfiles and multi-agent install already. I lose its skill browser and its community
  defaults. I gain tiers, which it does not have, and one source of truth instead of two.
- `skillOverrides` is Claude-specific. Codex gets the skills but not the tiering; every
  skill is visible there. Acceptable while Codex is the secondary harness — revisit if
  that flips.
- Copying means a target can drift from its source, and an edit made to an installed
  copy is silently lost on the next sync. Mitigated by hashing into the receipt so
  `status` reports drift, but not prevented. See ADR 0002.
- Upstream renames break entries. Deliberate: `sync` warns and `doctor` lists them, so a
  rename is a thing I decide about rather than a silent disappearance. This already
  caught six stale names on the first run.
