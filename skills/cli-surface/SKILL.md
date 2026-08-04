---
name: cli-surface
description: Design the CLI user-facing surface before implementation, including command tree, flags, output schema, exit codes, errors, help, and discoverability.
argument-hint: "@input file (any source describing what the CLI should do), or a free-text description; optional @existing-code references"
---

Design the **user-visible CLI contract** for a feature before any internal architecture is specified.
Produces a paired spec + screens artifact that downstream work (planning, implementation, review) can
consume. This phase answers *"what does the user see and script against?"* — not *"how is it wired
internally?"*. Surface design is most useful **before** the codebase shape has biased the design;
later validation passes can check it against reality.

### Path conventions used in this document

Paths fall into two scopes — keep them straight:

- **Target-project paths** (the repo this skill is invoked *against*): the binary's command-tree entry
  point (wherever the project keeps it), `docs/specs/output-spec.md` if present,
  `docs/specs/<binary>-cmd-output-spec.md` if present, and the chosen output directory for this
  skill's artifacts (default `docs/cli-surface/`).
- **Skill-bundled assets** (this skill's repo): `templates/screens.template.html`.

---
## Input

The argument after `/cli-surface` is one of:

1. **A file `@`-reference** — any document describing what the CLI should do: a feature spec, a PRD,
   a description, an existing-code reference, a sketch, notes. No particular format is assumed.
2. **A free-text description** — passed directly on the command line.
3. **Empty** — in which case the skill asks the user what to design.

Optional additional `@`-references pin existing code or supporting docs the design must respect.

```
# File input — output base name is derived from the input filename
/cli-surface @docs/features/team-management.md

# Free-text input — skill will ask for a base name
/cli-surface "design the `<binary> team` subcommand tree for creating, listing, and deleting teams"

# File input with an existing-code reference (when extending an existing subcommand tree)
/cli-surface @docs/features/team-management.md @<command-tree-entry-point>
```

---

## Steps

### 1. Validate and consolidate input

a. **If no input provided**, use **AskUserQuestion** (open-ended):

> "Please provide an input — a file describing what the CLI should do (any format), or a free-text
> description. Optional additional `@`-references can pin existing code the design must respect."

Do NOT proceed without an input.

b. **Read every `@`-referenced file completely.** No summaries, no truncation. Whatever the input
   document specifies about behaviour, constraints, and required output is normative for the surface.

c. **Identify the binary.** From the input or context, determine which CLI the surface attaches to. If
   unclear, use **AskUserQuestion**.

d. **Determine the output base name.**

   - **If the input is a file**: base name = the input filename with its extension stripped (e.g.
     `team-management.md` → `team-management`). Any awkward prefix patterns (timestamps, bracketed
     tags) are kept verbatim — the base is the user's filename, not a slug of it. Spec output is
     `<output-dir>/<base>.md`; screens output is `<output-dir>/<base>-screens.html`.
   - **If the input is free-text**: use **AskUserQuestion** to ask for a base name (a short kebab-case
     identifier). Do not proceed without one.
   - **Output directory**: default `docs/cli-surface/`. If a different location is conventional in this
     repo (visible from sibling docs structure), prefer the project's convention; ask the user if
     ambiguous. Create the directory if missing.

e. **Check for existing surface docs with the same base.** If `<output-dir>/<base>.md` exists:

- Use **AskUserQuestion** to ask:
  > "Existing surface design found: `<path>`. Update it in place, or pick a different base name?
  > (default: update)"
- **On update**: re-read both existing files (spec and screens), treat the new run as a revision, and
  update a `Last regenerated:` line in the document header.

   Re-invoking with feedback (the external feedback loop, see step 15) hits this branch by design —
   default to update so re-invocation is idempotent.

### 2. Read the project's CLI conventions

The surface MUST be consistent with the existing CLI style. Before designing, read in this order:

a. **`docs/specs/output-spec.md`** — if it exists, the normative stream/exit/format contract.

b. **`docs/specs/<binary>-cmd-output-spec.md`** — if it exists, the binary-specific elaborations.

c. **The existing command tree** — wherever this project keeps the binary's entry point and subcommand
   layout. Locate it from the project layout (common candidates: `cmd/<binary>/`, `src/cli/`,
   `bin/`, `app/cli/`, `packages/cli/`, a single-file entry script). Identify actual subcommands,
   shared flags, and error-message phrasing currently in production. The new design must extend this
   tree, not collide with it.

d. **Existing structured-output schemas** — search the codebase for prior `--format json` (or
   equivalent) output types in the host language so the new schema reuses established field-naming
   conventions (snake_case vs camelCase, timestamp format, etc.).

e. **Hint-system probe.** If `docs/specs/output-spec.md` was read in (a), determine whether the
   project documents a **hint system** — actionable next-step text emitted alongside error messages.
   Look for keywords like `Hint:`, "actionable", "next step", "remediation", or an explicit section
   describing how errors should suggest recovery. Record one of:

   - **Hints present** → the spec mandates hints. The Hint column in step 8 is required, the
     two-part error style in step 9a is required, and screens render hints (step 13's consistency
     check enforces this).
   - **Hints absent (or `output-spec.md` does not exist)** → hints are optional. The Hint column in
     step 8 is omitted, error style in step 9a is one-part (`Error: <noun> "<id>": <reason>`), and
     the screens consistency check skips the hint requirement. The designer MAY still add hints
     where they help; they are simply not contract.

   State the decision once in the spec doc (§0 Source artifacts).

If `<binary>-cmd-output-spec.md` does not exist for a new tool, note that authoring it is a separate
task and proceed using `output-spec.md` alone (or no spec, if neither exists — in which case the
surface doc carries the conventions it adopts).

### 3. Identify output variants

For every distinct user-visible situation this CLI must produce, name an **output variant**. Output
variants are the design unit of this skill: each variant is one row in the surface inventory and
becomes one (or more) screen(s) in step 13. They are derived from the input document, the conventions
read in step 2, and the designer's understanding of the feature.

Output variants typically span:

- **Happy paths** — successful invocations, one per significant subcommand or argument shape.
- **Format variants** — for any subcommand that supports `--format json` or other non-default
  formats, the structured-output rendering is a distinct variant from the default plain rendering.
- **Error paths** — one variant per distinct error class (validation, not-found, conflict, usage,
  permission, etc.).
- **State-changing variants** — confirmation prompts, `--dry-run`, `--yes`, `--force`, idempotent
  re-runs.
- **Discoverability variants** — `<binary>` (zero args), `<binary> <group>` (group-only), `--help`,
  unknown-subcommand error.
- **TTY-conditional variants** — color/no-color, piped output, non-interactive stdin.

Output this inventory as the `Output variants` table in §1 of the surface doc (template in step 12):

| #   | Variant                                         | Type            | Surface elements implied                                 |
|-----|-------------------------------------------------|-----------------|----------------------------------------------------------|
| V1  | Create a team — success                         | happy path      | subcommand + name positional + owner flag + result line  |
| V2  | Create a team — name conflict                   | error path      | exit code + stderr substring + error class               |
| V3  | List teams — default format                     | happy path      | subcommand + table layout                                |
| V4  | List teams — `--format json`                    | format variant  | structured schema                                        |
| V5  | Delete a team — confirmation prompt             | state-change    | prompt wording + `--yes` flag + TTY policy               |

Number variants (V1, V2, …) so screens and consistency checks can cite them directly. If the input
document carries its own structured units (e.g. acceptance criteria, scenarios, requirements), the
designer SHOULD trace each one to one or more variants in a sentence after the table — but the
canonical design unit is the variant, not the input's structure.

### 4. Identify the primary human workflow

Before designing flags or output formats, fix the **80% case**: the most common interactive
invocation a human will run, and what they'll see when they run it. This is the human-first gate —
without it, the surface can be fully specified, fully testable, and still awkward for the common
task.

a. **Most common user goal.** One sentence, business-language. Should align with one of the happy-path
   variants identified in step 3. Example: *"An operator sets up a new team and adds the first member,
   in a single short session."*

b. **Shortest happy-path invocation.** The literal command line a competent first-time user would
   type to achieve the goal. No shell aliases, no environment-variable cheats. Example:

```
$ <binary> team create ops --owner alice@example.com
```

c. **Input acquisition table.** For every required input the primary workflow needs, name exactly one
   acquisition strategy:

| Input          | Strategy                              | Notes                                  |
|----------------|---------------------------------------|----------------------------------------|
| team name      | `positional` (arg 1)                  | required; no default                   |
| owner email    | `required-flag --owner`               | also `<BINARY>_OWNER` env var          |
| description    | `prompt-on-TTY` (skip if `--description` given) | optional; non-interactive: omit         |
| confirmation   | `n/a`                                 | not destructive; no prompt             |

   Strategies (pick exactly one per input):

   - `positional` — argv position; arity stated.
   - `required-flag` — must be passed via flag; document env-var binding if any.
   - `prompt-on-TTY` — when stdin is a TTY *and* the input wasn't supplied via flag/env/positional,
     prompt the user. When stdin is **not** a TTY (script, pipe, CI), the input is required via
     flag/env/positional and absence is a hard failure (exit 2 with a missing-input error).
   - `env-var` — accepted from a named environment variable; document precedence vs. flag.
   - `hard-fail-non-interactive` — never prompted; absence always fails (use this for inputs that have
     no sensible interactive default).

   **CLIG bias**: prefer `prompt-on-TTY` over `hard-fail` for missing non-dangerous inputs when a
   sensible interactive answer exists. Scripts pass the flag; humans get prompted.

d. **First success line.** The literal first thing the user sees on stdout/stderr when the primary
   workflow succeeds. Name the entity, confirm what happened, no fluff.

```
S| Created team "ops" (id: tm_4f3a). Owner: alice@example.com.
```

e. **First failure line for the most likely error.** The literal first thing the user sees when the
   most common error occurs (typically: name conflict, validation failure, or missing-input on
   non-interactive stdin). Include the actionable hint **only if the hint system was found in step
   2e**; otherwise show the one-part form.

   *Two-part form (hints present):*
   ```
   E| Error: team "ops": already exists.
   E|   Hint: run `<binary> team list` to see existing teams, or choose a different name.
   ```

   *One-part form (hints absent):*
   ```
   E| Error: team "ops": already exists.
   ```

Output this whole block as section §2 ("Primary human workflow") of the surface doc. Subsequent design
steps (command tree, flags, output, errors) are then evaluated against this baseline: if a design
choice makes the primary workflow harder, flag it.

### 5. Design the command tree

a. **Verb/noun layout.** Choose between:

- *Noun-first*: `<binary> team create`, `<binary> team list` (preferred when the noun has ≥3
  operations — groups discoverability under `<binary> team --help`).
- *Verb-first*: `<binary> create-team`, `<binary> list-teams` (acceptable when only one or two
  operations exist and grouping would be premature).

State the choice and the rationale. If extending an existing tree, the choice is whatever the existing
tree uses — no mid-tool style mixing.

b. **Subcommand inventory.** One row per subcommand:

| Path                         | Purpose (one line)              | Variants covered |
|------------------------------|---------------------------------|------------------|
| `<binary> team create`       | Create a new team               | V1, V2           |
| `<binary> team describe`     | Show details for a team         | V6               |
| `<binary> team delete`       | Remove a team                   | V5, V7           |

c. **Aliases.** Only when there is a documented user need (long names tedious in scripts, prior tool
   established the alias). Each alias gets a justification. Default to no aliases.

d. **Position in the broader tree.** Show the diff against the existing `<binary> --help` listing —
   what is added, what (if anything) is renamed or moved. Renames or moves to existing commands need a
   separate migration plan and are out of scope for the surface doc; flag and stop.

### 6. Design the flag set per subcommand

For each subcommand from step 5, produce a flag table:

| Long             | Short | Type     | Default | Required | Env var               | Mutex group | Notes |
|------------------|-------|----------|---------|----------|-----------------------|-------------|-------|
| `--name`         |       | string   | —       | yes      | `<BINARY>_TEAM_NAME`  |             | name of the team |
| `--description`  | `-d`  | string   | `""`    | no       | —                     |             | free-form description |
| `--output`       | `-o`  | enum     | plain   | no       | —                     |             | `plain\|json` per output-spec |
| `--yes`          | `-y`  | bool     | false   | no       | —                     |             | skip confirmation prompt |
| `--dry-run`      |       | bool     | false   | no       | —                     | `--yes`     | preview only; mutually exclusive with `--yes` |

**Rules**:

- **Long form is canonical.** Short forms only for very common flags; document the full rationale —
  short flags are cheap to add but expensive to remove (breaking change).
- **Env var bindings** follow the project's existing convention (typically `<BINARY>_<FLAG>` in upper
  snake-case). Precedence MUST be: explicit flag > env var > default. State this once at the top of
  the doc; do not re-state per flag.
- **Reserve common flags** to the binary's root command, not subcommand: `--output/-o`,
  `--quiet/--verbose/--debug`, `--config` if the tool reads config. The doc lists these once at the top
  and per-subcommand tables only repeat them when behavior diverges.
- **Mutex groups** are explicit in the table. Most CLI frameworks support mutex groups; the surface doc
  names the constraint, not the framework call.
- **Booleans default false** unless there is a documented reason otherwise (negation-default flags are
  confusing — prefer `--no-cache` over `--cache=false`).

### 7. Design the output schema and stream contract

a. **Per subcommand, declare the output mode** with a one-line **Rationale** explaining why the chosen
   default format is the easiest to scan for a human at a terminal:

| Subcommand                | Default-format result                 | Rationale (why this is clearest)                                                | `--format json` schema ref | Side-effect-only? |
|---------------------------|---------------------------------------|----------------------------------------------------------------------------------|----------------------------|-------------------|
| `<binary> team create`    | one-line "Created team `<id>`"        | confirms the action and exposes the new id in one scannable line                  | §5.b TeamRef               | no                |
| `<binary> team delete`    | (empty stdout per output-spec)        | side-effect-only; success signaled by exit 0 (see step 13's design-flag banner)   | §5.b OkStatus              | yes               |
| `<binary> team list`      | aligned table                         | typical run returns < ~50 rows; columns scan faster than per-line key:value       | §5.b TeamList              | no                |
| `<binary> team describe`  | key:value block                       | single-record detail; labelled rows beat a one-row table for readability          | §5.b TeamDetail            | no                |

**Per-subcommand TTY-aware behavior** (one row per subcommand, `n/a` with rationale when not
relevant):

| Subcommand              | TTY-aware behavior                                              |
|-------------------------|------------------------------------------------------------------|
| `<binary> team list`    | column widths auto-fit to terminal width; piped output → fixed   |
| `<binary> team describe`| color/emphasis only when stdout is TTY (per color rules)         |
| `<binary> team create`  | n/a — single-line output unaffected by TTY                       |
| `<binary> team delete`  | n/a — no stdout                                                  |

   Anything beyond column widths and color (paging, spinners, progress bars, redraws) is **out of
   scope for screens** — describe in prose in the screens file's optional non-textual section, not
   modeled here.

b. **Define the JSON schema for each non-trivial structured output.** Use a struct table or Mermaid
   class diagram. Field naming follows the project's existing convention (snake_case unless the
   project uses camelCase project-wide — check step 2.d findings).

   ```
   TeamDetail
   ├─ id          string  — opaque team identifier
   ├─ name        string  — user-supplied, unique
   ├─ created_at  string  — RFC3339
   └─ members     []Member
       ├─ user_id     string
       └─ role        string  — one of: owner | maintainer | member
   ```

   **Stability label per field**: `Contract` (versioned, breaking change requires a deprecation
   window) or `Convenience` (may change at minor version). Default is `Contract` for any field
   appearing in `--format json` output.

c. **Re-state `output-spec.md` compliance** for this command (skip if no spec exists):

- *stdout vs stderr* — confirm the chosen result/progress split conforms to the spec.
- *side-effect-only* — if the command produces no semantic result, declare it and define the
   minimal `--format json` payload.
- *errors under `--format json`* — declare whether a structured error object is emitted to stdout.

### 8. Design the exit-code map

For each subcommand, list every non-zero exit code with documented semantics. **Include a Hint column
only if step 2e found a hint system in `output-spec.md`.** When hints are required, each row's Hint is
a literal string, `n/a` with one-sentence rationale, or `see <docs path>` for complex cases. Silently
omitting the hint when the spec requires it is a fault.

*With hints (when step 2e found a hint system):*

| Code | Class              | Trigger                                                | stderr substring (canonical)              | Hint                                                                  |
|------|--------------------|--------------------------------------------------------|-------------------------------------------|-----------------------------------------------------------------------|
| 0    | success            | normal completion                                       | —                                         | n/a — success                                                          |
| 1    | generic failure    | unclassified runtime error                              | varies                                    | n/a — error class is not specific enough to suggest one next step      |
| 2    | usage error        | missing/invalid flag, unknown subcommand                | starts with `Error: ...`                  | `run \`<binary> <subcommand> --help\` for usage`                       |
| 64   | validation         | input failed business validation                        | "team name `<name>` is invalid: ..."      | `team names must match \`[a-z][a-z0-9-]{1,30}\``                       |
| 65   | not-found          | referenced resource does not exist                      | "team `<id>` not found"                   | `run \`<binary> team list\` to see existing teams`                     |
| 73   | conflict           | unique-constraint or concurrent-modification clash      | "team `<id>` already exists"              | `run \`<binary> team list\` to confirm, or choose a different name`    |

*Without hints (when step 2e did not find a hint system):*

| Code | Class              | Trigger                                                | stderr substring (canonical)              |
|------|--------------------|--------------------------------------------------------|-------------------------------------------|
| 0    | success            | normal completion                                       | —                                         |
| 2    | usage error        | missing/invalid flag, unknown subcommand                | starts with `Error: ...`                  |
| 64   | validation         | input failed business validation                        | "team name `<name>` is invalid: ..."      |
| ...  | ...                | ...                                                     | ...                                       |

**Rules**:

- **Codes are part of the contract.** Once published they cannot be repurposed; new triggers get new
  codes.
- **Stay under 125.** 126 / 127 / 128+N are reserved by POSIX shells.
- **Reuse codes across the binary.** Check whether the binary publishes a master exit-code map (a
  central document — `<binary>-cmd-output-spec.md` or whatever the project calls it — that lists every
  code used by the binary). If one exists, this skill adds rows to it rather than reinventing per
  feature. If no master map exists, propose the codes here and flag that the map should be promoted
  to a spec in a follow-up; do not require a master map to exist before the surface can be designed.
- **Usage errors are exit 2 by convention.** Most CLI frameworks emit exit 2 on missing/invalid flag
  and unknown-subcommand errors. Do not specify exit 1 for those.

### 9. Design error message style, help, and discoverability

a. **Error message style.** The phrasing rule depends on whether step 2e found a hint system:

   *Hints present — two-part phrasing:*
   ```
   Error: <noun> "<identifier>": <reason>
     Hint: <actionable next step — when applicable>
   ```

   *Hints absent — one-part phrasing:*
   ```
   Error: <noun> "<identifier>": <reason>
   ```

   Examples (two-part):

   - ```
     Error: team "ops": already exists
       Hint: run `<binary> team list` to confirm, or choose a different name.
     ```
   - ```
     Error: file "/etc/<binary>/config.yaml": not readable: permission denied
       Hint: check file ownership, or pass `--config <path>` to use a different file.
     ```

   **Rules**:

   - **Every error message MUST name the offending identifier** (team name, file path, flag name)
     literally. Downstream test assertions rely on this.
   - **When hints are required (step 2e):** every error class in the exit-code map MUST have a Hint
     entry (literal string, `n/a` with one-sentence rationale, or `see <docs path>`). The Hint exists
     to help a human user recover, not to satisfy a checklist — prefer concrete suggestions over
     vague advice. The Hint line is indented two spaces and prefixed with `Hint:`. Stability: the
     `Error:` line wording is `Convenience`; the exit code is `Contract`; the `Hint:` line is
     `Convenience`. Scripts MUST NOT depend on hint substrings.
   - **When hints are not required:** the designer MAY still add hints where they materially help, but
     they are not contract and consistency checks do not enforce them.

b. **Help text shape.** Each subcommand has:

- *Short* (one line, sentence case, no trailing period — common CLI convention) for parent listings.
- *Long*: one paragraph **followed by an `Examples:` block first**, then the flag listing. Examples
  come before the dense flag table because a first-time user needs the one-line-that-works before they
  can absorb every flag's semantics. The block contains at least one primary-workflow happy-path
  invocation (matching step 4b) and one `--format json` invocation. For commands with non-trivial
  options, add a third example showing the most common variant.

   The doc includes the *Short* and *Long* drafts **verbatim** — do not punt to "TBD during
   implementation." The examples come from step 4 and the spec's flag table; copy, don't reinvent.

c. **Discoverability and zero-input behavior**:

- *No-arg behavior*: state what `<binary>` (zero args) prints. Common choices:
  *(i)* concise top-level help with subcommand list and exit 0;
  *(ii)* same plus a one-line "Run `<binary> --help` for more" banner;
  *(iii)* usage stub and exit 2.
  Pick one with a one-line rationale. Same decision for `<binary> <group>` (e.g., `<binary> team`
  with no further subcommand) when the tree uses noun-first grouping.
- *Missing-input behavior*: state what `<binary> <subcommand>` prints when required inputs are absent
  **on a non-interactive stdin** (the interactive case is covered by step 4c's `prompt-on-TTY`
  strategy). Choices: *(i)* the canonical error message (+ Hint if required) + exit 2; *(ii)* the
  error + a usage stub + exit 2; *(iii)* the error + the full Long help + exit 2. Pick one. Default
  is *(i)* unless the help body materially helps recovery.
- *`help` subcommand*: declare whether `<binary> help` and `<binary> help <subcommand>` are part of
  the contract (git-style discoverability). Default: yes when the tree has ≥3 subcommand groups;
  otherwise no. State the decision either way.
- *Support and docs path*: every Long help block ends with a one-line pointer to the project's real
  docs URL and issues/feedback URL. This is the user's escape hatch when help isn't enough; omitting
  it is a fault.
- *Completion*: state which shells the binary supports (`<binary> completion bash|zsh|fish|powershell`
  is a common convention across modern CLI frameworks). Default: support all four;
  deviate only with rationale.
- *Man pages*: state whether the binary publishes man pages. If yes, point at the existing generation
  tooling.
- *Tree listing*: confirm the new subcommands appear in `<binary> --help` and the relevant
  group-level help (`<binary> team --help`, etc.).

d. **Color and TTY behavior.** State, once for the whole surface:

- Which output elements are colored, with three pieces per element:
  *(i)* the token (e.g., `Error:` label, image names, version strings),
  *(ii)* the ANSI color (red / yellow / green / etc., with the literal sequence `\e[31m…\e[0m` in
  parentheses for unambiguity),
  *(iii)* the screens-template CSS class or per-design alias used to render it (`error-label`,
  `fg-yellow` via `.image-name`, etc.).
  Format as a small table — the screens consistency check (step 13d) verifies every colored token in
  screens has a matching row here.
- The TTY-detection rule: color is emitted only when the relevant stream is a TTY *and* the
  `NO_COLOR` environment variable is unset. Both stdout and stderr are checked independently (an
  error to a non-TTY stderr is not colored even if stdout happens to be a TTY).
- `--no-color` / `--color=always|never|auto` flag policy. Default policy: respect `NO_COLOR` and TTY
  detection automatically, no flag needed unless the design has a documented reason.
- **Out of scope for this surface phase**: cursor movement, screen clears, line redraws, in-place
  spinners, progress-bar animation. If the design needs any of those, flag it and split into a
  separate "interactive UX" follow-up — they are not modeled in screens (see step 13), only described
  in prose in the screens file's optional non-textual section.

### 10. Design confirmation, `--dry-run`, and idempotence

For every subcommand that writes or destroys state:

a. **Idempotence statement.** "Running this command twice with the same arguments produces the same
   end state." Yes / No / Yes-with-caveats.

b. **Confirmation prompt.** Default for destructive commands is *prompt unless `--yes` provided*.
   Non-interactive sessions (no TTY on stdin) refuse without `--yes`. State exactly which subcommands
   prompt.

   **Note**: prompts for missing *non-dangerous* inputs are designed in step 4c (the
   primary-workflow input-acquisition table), not here. This step covers safety prompts only — "are
   you sure?" before an action is taken — distinct from "what value?" prompts for missing required
   input. Mixing the two is a design smell; one is a yes/no gate, the other is an input-acquisition
   strategy.

c. **`--dry-run`** for any command whose effect is non-trivial to reverse. Specify:

- Output format under dry-run (typically the same shape as the real command, but with a
  `dry_run: true` field in `--format json` output and a `[DRY RUN]` prefix on plain output).
- Exit codes under dry-run (validation errors still fail; the action itself never runs).

d. **`--force`** only when the prompt-driven default is too intrusive for the common case. Document
   the difference between `--yes` (skip confirmation) and `--force` (override safety checks).
   Conflating them is a common source of bugs.

### 11. Compliance check against `output-spec.md`

If `output-spec.md` exists, run a compliance pass. Each row of the checklist is either ✅ (the design
conforms) or ⚠ `Exception:` with one-paragraph rationale. Silent divergence is a fault. If the spec
does not exist, replace this step with a short "Conventions adopted" subsection that states the
defaults this design picks (streams, formats, exit codes, verbosity) and flags that promoting them to
a spec is a follow-up.

Typical rows (adjust to whatever sections the project's spec actually contains):

| Spec rule                                                                       | Status / Exception |
|---------------------------------------------------------------------------------|--------------------|
| stdout reserved for results; no logs/progress/diagnostics on stdout              |                    |
| stderr used for progress/diagnostics; not a stability contract                   |                    |
| structured commands support `--format json`; default is `plain`                  |                    |
| structured output not interleaved with logs in the same stream                   |                    |
| `--quiet` does not suppress stdout; `--debug` does not alter stdout              |                    |
| verbosity flags affect stderr only                                               |                    |
| exit codes independent from logs; errors logged to stderr regardless of format   |                    |
| `--format json` MAY emit structured error to stdout; exit code authoritative     |                    |
| side-effect-only commands print nothing to stdout under default format           |                    |
| side-effect-only commands emit minimal result object under `--format json`       |                    |

### 12. Assemble the surface document

Document layout (one file):

```markdown
# CLI Surface: <Feature Title>

## 0. Source artifacts
- Input: `<input file>` (or `inline description`)
- Binary: `<binary>` (entry point: `<path to command tree>`)
- Conventions consulted:
  - `docs/specs/output-spec.md` (or "absent")
  - `docs/specs/<binary>-cmd-output-spec.md` (or "absent — author as follow-up")
  - existing tree under `<command tree path>`
- Hint system: `required` (per `output-spec.md`) / `optional` (no spec, or no hint system documented)

## 1. Output variants
[Step 3 inventory table with V1, V2, … numbering]

## 2. Primary human workflow
[Step 4: most common user goal, shortest happy-path invocation, input-acquisition table,
first success line, first failure line (with hint if required). Subsequent design choices are
evaluated against this baseline.]

## 3. Command tree
[Step 5 layout, inventory table, alias decisions, tree-diff]

## 4. Flag set per subcommand
[Step 6 per-subcommand flag tables + global precedence rule]

## 5. Output schema and stream contract
[Step 7 per-subcommand mode table with Rationale column + TTY-aware behavior table +
JSON schemas + per-command output-spec compliance]

## 6. Exit-code map
[Step 8 table; with Hint column iff step 2e found a hint system]

## 7. Error message style, help, and discoverability
[Step 9: error-message style (two-part or one-part per step 2e), Short/Long help drafts verbatim
(examples-first ordering), no-arg behavior, missing-input behavior, help subcommand decision,
support/docs path, completion, man notes]

## 8. Confirmation, dry-run, idempotence
[Step 10 per-subcommand statements; cross-references step 4c for missing-input prompts]

## 9. Stability promises
| Element                          | Stability    |
|----------------------------------|--------------|
| Subcommand names + tree position | Contract     |
| Long flag names                  | Contract     |
| Short flag names                 | Contract     |
| `--format json` field names      | Contract     |
| `--format json` field types      | Contract     |
| Exit codes                       | Contract     |
| Error message stderr substrings  | Convenience  |
| Hint substrings (if applicable)  | Convenience  |
| Plain (default) output text      | Convenience  |
| stderr progress text             | Convenience  |

## 10. Color and TTY behavior
[Step 9d: a table of (token, ANSI sequence, screens-template CSS class / alias). NO_COLOR / TTY
detection rule. `--no-color` / `--color` flag policy. Out of scope: cursor movement, screen
clears, spinners.]

## 11. `output-spec.md` compliance (or "Conventions adopted" if no spec)
[Step 11 checklist; every row ✅ or ⚠ Exception with rationale]

## 12. Open questions for downstream work
- [Anything the surface deliberately punts on, e.g. "concurrent-edit semantics surfaced as exit code
  73 'conflict' but the locking strategy is left for the implementation phase."]
```

### 13. Render screens per output variant

The spec is the source of truth; **screens are the rendered output a human reviews to give
feedback**. They are derived from the spec, not authored independently. Every literal in a screen
(subcommand name, flag form, stdout text, stderr text, exit code, color choice) traces to a row in
the spec. If a reviewer wants a screen to change, the spec changes and the screens re-render — never
the reverse (see guardrails).

Screens are rendered as **a single self-contained HTML file** (one per session) — not markdown — so
colors, dim/bold styling, and stream-prefix tinting actually render in a browser when the reviewer
opens it. The HTML is plain static markup with embedded CSS, no external dependencies, no JavaScript.

a. **Output file**: `<output-dir>/<base>-screens.html` (same base as the spec, `-screens.html`
   suffix, same directory).

b. **How to fill in the template**: copy `templates/screens.template.html` and follow the rendering
   rules embedded as comments at the top of that file. The template is the canonical authority for
   per-screen HTML structure, side-effect-only treatment, color application, hint-line rendering, and
   out-of-scope items. Read those rules in full before rendering — do not infer them from examples.

c. **Coverage rule**. The HTML file MUST include:

- One `<section class="variant">` per output variant in the spec.
- One screen per error class in the spec's exit-code map (showing the canonical stderr substring and
  exit code).
- Both default-format and `--format json` invocations of at least one happy-path command per
  subcommand (so the JSON schema is shown literally).
- One screen each for: confirmation prompt, `--dry-run`, `--yes` — wherever the design uses them.
- For commands that color output: at least one screen exercising the spec's color palette via the
  appropriate classes/aliases.

The file MUST NOT enumerate every flag combination — it is a sampler, not a combinatorial test plan.
If a reviewer asks "what about flag X with value Y," that is a spec question (answered by the flag
table), not a screens question.

d. **Consistency check before saving** the screens file:

- Every subcommand named in the screens appears in the spec's command-tree inventory.
- Every flag form in the screens appears in the spec's flag tables.
- Every exit code in the screens appears in the spec's exit-code map.
- Every stderr error substring matches the spec's error-message style rule and named identifier
  convention.
- **If hints are required (step 2e):** every error screen renders the corresponding Hint from the
  exit-code map (using `.hint-label` + `.hint-text`), unless the map entry is `n/a` with rationale.
  If hints are optional, this check is skipped.
- Every CSS class used in the screens exists either in the template's catalog or in the per-design
  aliases block — and every alias maps to a `--fg-*` variable from the catalog.
- Every colored token in the screens corresponds to a "Color and TTY behavior" entry in the spec.
- No inline `style=` attributes on any element inside `<div class="terminal">`.
- Every subcommand the spec marks as side-effect-only has a screen with an empty terminal body (only
  the prompt line) AND a `<div class="design-flag">` banner after the exit line. No `S| (no output …)`
  lines anywhere.
- The primary-workflow happy-path invocation (step 4b) is rendered as a dedicated screen, matching
  the spec's first-success-line wording (step 4d) verbatim.
- The primary-workflow first-failure-line invocation (step 4e) is rendered as a dedicated screen,
  matching the spec's wording verbatim, with the hint included only if hints are required.
- Every output variant in the spec has at least one screen.
- Every error class in the spec's exit-code map has at least one screen.
- The example `<section class="variant">` from the template has been replaced (not left in alongside
  the real screens).

A screens file that fails any of these checks is a fault — fix the spec or the screens, never let
them drift.

### 14. Save and announce

a. **Spec file**: write to `<output-dir>/<base>.md` (base derived in step 1d).

   **On update of an existing file** (step 1e branch): preserve the filename. Update a
   `Last regenerated: YYYY-MM-DDTHH:MMZ` line in the spec header.

b. **Screens file**: write to `<output-dir>/<base>-screens.html`. Produced by copying
   `templates/screens.template.html` and filling it in per step 13.

c. **Write both files atomically** — never write the spec without the screens.

d. **Show summary**:

```
✅ CLI surface design complete:
   - Spec:    <output-dir>/<base>.md
   - Screens: <output-dir>/<base>-screens.html   ← open in a browser to review

📋 Surface coverage:
   - Subcommands designed:    <count>
   - Flags total:             <count> (long), <count> (short)
   - Exit codes added:        <count>
   - JSON schemas:            <count>
   - Output variants:         <count>
   - output-spec exceptions:  <count> (each with rationale)
   - Hint system:             required / optional / n/a

🎬 Screens coverage:
   - Variants with at least one screen:  <count>/<total>
   - Error-class screens:                <count>
   - --format json screens:              <count>
   - Confirmation/dry-run/yes:           <count>

🔗 Next step (after review):
   • If approved → the spec is ready to feed into downstream work (planning, implementation, review).
   • If you want changes → re-invoke /cli-surface with feedback as additional argument. The skill
     detects the existing files and updates them in place.
```

### 15. Hand off for external review

The skill stops here. The screens file is the human-review artifact; the user reads it and either
approves (and proceeds to whatever downstream step their workflow uses) or re-invokes `/cli-surface`
with feedback. Do **not** loop on `AskUserQuestion` for review — review happens externally, the skill
is idempotent across re-invocations (step 1e).

State this once to the user:

> "Surface design saved. Please review the screens file (`<path>`) and either:
>  • re-invoke `/cli-surface` with feedback for changes, or
>  • proceed to the next step of your workflow (planning, implementation, review)."

---

## Output

Two paired files in the chosen output directory, sharing a base filename, written together:

1. **`<base>.md`** — the spec. Contents per step 12 layout.
2. **`<base>-screens.html`** — the review artifact (human-reviewed). Contents per step 13.

Re-invocation with feedback updates both files in place (step 1e).

---

## Guardrails

**Inputs and scope**

1. No input → do not proceed.
2. Surface = observable contract only. Service classes, repositories, query patterns, and error-class
   hierarchies belong to downstream implementation work. A spec naming a `TeamService` or a `teams`
   table has crossed the seam.
3. Every output variant maps to at least one surface element. The inventory table (step 3) is the
   gate — silent omission is a fault.
4. Do not propose renaming or moving an existing subcommand inside this skill. Flag and request a
   separate migration plan.

**`output-spec.md` compliance**

5. `output-spec.md`, if present, is normative across all CLIs — never advisory. Reference and check;
   do not duplicate. If absent, the surface doc explicitly states the conventions it adopts.
6. Every compliance-checklist row is ✅ or ⚠ with a written `Exception:` rationale. Silent divergence
   is a fault.
7. Cite the binary's existing `<binary>-cmd-output-spec.md` exit-code map if present; add rows, do
   not redefine existing codes. New codes never reused across triggers within one binary.

**Hint system**

8. Probe `output-spec.md` (step 2e) before assuming hints are required. Forcing the Hint column and
   two-part error style on a project that does not document a hint system is incorrect.
9. When hints are required, every error class has a Hint (literal string, `n/a` with one-sentence
   rationale, or docs pointer). When hints are optional, the designer MAY still add them where they
   materially help — but they are not contract and not enforced.

**Command tree, flags, exit codes**

10. Inspect the existing tree before naming a new subcommand. Style drift across one binary is a
    contract bug.
11. Long flags canonical; short flags only with named rationale (very common, prior tool used it,
    scriptability). A short flag is a contract — removing it later is breaking.
12. Usage errors are exit 2 by convention. Specifying exit 1 for missing flags will diverge from the
    runtime unless the framework's error handling is explicitly customized and documented.
13. Help-text Short/Long drafts authored verbatim in the doc — never "TBD".

**Errors, confirmation, primary workflow**

14. Default plain-output format requires a one-line Rationale explaining why it scans easiest for a
    human. "Aligned table" without justification picks the wrong default for narrow records or huge
    collections.
15. Missing-input behavior: prefer `prompt-on-TTY` for non-dangerous inputs (step 4c) over hard-fail.
    Scripts pass the flag; humans get prompted. Decision is per-input.
16. Destructive commands declare idempotence and confirmation policy explicitly. `--yes` skips a
    prompt the user would have answered yes to; `--force` overrides a safety check the system should
    not normally bypass. Never conflate.
17. Do not skip the primary-workflow gate (step 4). If the happy-path invocation is more than ~3
    tokens, push back on positional/flag/prompt decisions before signing off.

**Screens**

18. Screens render the spec; never authored independently. Every literal (subcommand, flag, stdout
    text, stderr text, exit code, color) traces to a spec row. If a reviewer wants a screen line to
    change, the spec changes and the screens re-render.
19. Spec + screens are written atomically — never one without the other.
20. Always copy `templates/screens.template.html` and follow the rendering rules embedded at the top
    of that file. The template is the canonical authority for per-screen structure, side-effect-only
    treatment, color application, hint-line rendering, and out-of-scope items. Never write the HTML
    from scratch and never duplicate the template's rules into the spec or this skill.

**Re-invocation and hand-off**

21. On update of an existing file (step 1e), preserve the filename; record the regeneration time in a
    header line.
22. Do not auto-invoke any downstream step. Review happens externally (step 15).

**Context integrity (MUST-reads)**

23. Read every `@`-referenced file completely. Read `docs/specs/output-spec.md` in full when it
    exists. Read the screens template (`templates/screens.template.html`) in full — including the
    embedded rendering rules at the top. Partial reads cause surface gaps, missing compliance rows,
    and screen drift.
