---
name: package-design
id: package-design
category: Documentation
description: Generate package design PACKAGE.md charters for one or more packages/modules in any language.
---

Generate `PACKAGE.md` charters for one or more packages (or the equivalent unit of code organisation in
the project's language — module, crate, namespace) in this repo. Each charter describes the package's
design position — its scope, where its domain vocabulary lives (if any), the concept it owns, what it
explicitly does **not** own, and how to evolve it without drift. Domain vocabulary itself is not
duplicated here: it lives in `CONTEXT.md` files when warranted (per the project's context-map criterion).
The `PACKAGE.md` either points to the relevant `CONTEXT.md` or explains in one short sentence why none
exists. Every charter ends with a `Clean-concept rating` section: a one-line pass note when the package
is single-concept, or a detailed rating with findings when it fails the single-concept smell test
(defined below), so the design debt is visible to the next reader.

This skill is language- and project-agnostic. Wherever the steps below mention language-specific
artefacts (manifest files, source-file extensions, error types, etc.), translate them to the host
language's equivalent. The term "package" is used throughout to mean *whatever this project calls a unit
of code organisation*: a directory of source files in Go/Python/Rust, a Java/Kotlin package, a TypeScript
module, an Elixir application, etc.

**Batch is the default.** This skill is normally invoked over a set of packages (a subtree, a glob, or
every package in the repo) so that the resulting charters are consistent with each other. Single-package
invocation is supported but is the degenerate case.

**Input**: The argument after `/package-domain` is one of:

1. **One or more package paths** — space-separated. Directory paths or language-native identifiers
   (import paths, module names, namespaces) are both accepted and may be mixed.
2. **A glob** — expanded relative to the repo root, e.g. `src/workspace/*` or `lib/stacks/**`. Standard
   shell globbing; `**` matches any depth.
3. **`--all`** — every package under the project's source roots, excluding test-data, generated, and
   vendor directories. Detect roots from the project layout (common candidates: `src/`, `lib/`,
   `internal/`, `pkg/`, `cmd/`, `app/`, `packages/*`); if the layout is ambiguous, ask the user.
4. **Empty** — in which case ask the user which packages to document.

**Examples** (paths shown are illustrative; substitute whatever your project uses):

```
# Single package (degenerate case)
/package-domain src/workspace/image

# Several specific packages
/package-domain src/dag src/dagrun src/failure

# A subtree
/package-domain src/workspace/*

# Every package in the repo
/package-domain --all
```

**Order in the workflow**: This is a self-contained documentation skill. It does not depend on any other
skill or wave. The package's own source code is the authoritative input. If the project happens to
maintain an auxiliary conceptual index (e.g. a responsibility map, type-index, glossary, or domain
model), use it as a supporting reference — but never as a substitute for reading the code.

**Steps**

1. **Resolve the target package set**

   a. If no input was provided, use the **AskUserQuestion tool** (open-ended) to ask which packages the
      charters are for (accepting any of the input forms listed above). Do not proceed without an
      answer.

   b. **Expand the input into a concrete list of package directories.** Glob patterns are expanded
      relative to the repo root; `--all` discovers every package under the project's source roots.
      Filter out:
        - directories whose path includes the project's test-data / fixtures / vendored-deps
          conventions (e.g. `testdata/`, `fixtures/`, `__fixtures__/`, `vendor/`, `node_modules/`,
          `target/`, `build/`, `dist/`);
        - directories with no source file in the project's primary language(s);
        - directories that are pure test packages (every source file is a test file by the language's
          convention — e.g. `_test.go`, `*.test.ts`, `test_*.py`, `*Spec.scala`).

   c. **Read the project's module/package identifier**, if the language exposes one. Examples: Go's
      `go.mod` (`module <path>`), Node's `package.json` (`name`), Rust's `Cargo.toml` (`[package] name`),
      Python's `pyproject.toml` (`[project] name`) or `setup.cfg`. For each remaining directory, derive
      its canonical identifier (import path, module path, namespace, or — if the language has none —
      just the repo-relative directory) and record both forms when both exist.

   d. Announce the resolved set to the user: number of packages and the list, so they can confirm before
      the work begins. For sets of fewer than 6 packages, list every path; for larger sets, list the
      first 5 and the total count. Continue without confirmation only if the user explicitly used
      `--all` (treated as opt-in to bulk).

   e. **For each package in the set**, check whether a `PACKAGE.md` already exists. If it does, read it
      in full and earmark any hand-written section (e.g. `## Additional notes`) for preservation — the
      new charter must be a strict improvement.

   The remaining steps (2–5) are applied **per package**, in the order resolved by Step 1b. Steps 6–8
   are run once across the full set after every charter is written.

2. **Read the package code (authoritative source)**

   a. List the package's source files (excluding test files and anything under test-data / fixtures /
      generated-output directories). Read **all** of them. The code is the only authoritative input — it
      reveals globals, abort sites, hidden helpers, dead state, and capabilities that any external index
      would miss (e.g. ANSI colour handling, TTY detection, file-tail helpers).

   b. While reading, capture for later use:
        - every public/exported type, function, method, and constant (by the language's visibility
          rules — `Exported` in Go, `public`/`pub` in Java/Rust, top-level non-underscore names in
          Python/TS, etc.);
        - any package- or module-level mutable state (globals, `var`s, singletons, class-level mutable
          fields) — flag these;
        - every abort/crash site and its message: the language's idiomatic "this should not happen"
          mechanism — `panic`, `throw`, `raise`, `assert`, `unreachable!`, `abort()`, `process.exit`,
          etc.;
        - any doc-comment lines that explicitly state a concept or responsibility (look for keywords
          like "concept", "owns", "canonical", "responsibility");
        - any inline comments admitting smells (e.g. `// not good`, `// TODO`, `// hack`, `# XXX`,
          `# FIXME`);
        - exit-code values, error-code constants, or status enums returned from CLI/process entry points
          (only relevant if the package is an entry point);
        - the package's actual dependencies, filtered to project-internal packages. Source them from the
          language's native mechanism: imports/use-statements/requires/manifest-declared deps. These
          become the upstream list.

   c. To discover the downstream list, search for references to this package across the repo (excluding
      the package itself). Use the form callers would write — import path, module name, namespace, or
      relative path — and group consumers by their containing package.

   d. **Optional supporting references.** If the project maintains an auxiliary conceptual index (e.g. a
      responsibility map, type-index, glossary, domain model, or architecture doc) and it covers this
      package, read the relevant portion and cite it in `## See also`. Do not treat it as a substitute
      for the code in Step 2a; use it only to corroborate or enrich findings already grounded in the
      code.

3. **Write the PACKAGE.md sections**

   Use this exact section order and headings. Hard-wrap every line at 120 characters.

   ```markdown
   # `<canonical identifier>` — <one-line package summary>

   ## Glossary
   <Exactly one of the following. Choose by inspecting the filesystem and the project's
   context-map criterion (see project root `CONTEXT-MAP.md` if it exists).>

   - **This package has its own `CONTEXT.md`** (shared-kernel or other context with its own
     glossary):
     `See [`CONTEXT.md`](./CONTEXT.md) for this package's domain vocabulary.`
   - **This package is a sub-package of a context with a `CONTEXT.md`** (e.g. a sub-package of a parent
     directory whose `CONTEXT.md` exists):
     `Domain vocabulary lives in [`<parent>/CONTEXT.md`](<relative-path>/CONTEXT.md).`
   - **No `CONTEXT.md` anywhere applies** — write one short sentence explaining why. The justification
     stands on its own; do not cite ADRs or external rules. Examples:
       - `No CONTEXT.md for this package: its types are technical primitives whose semantics are fully
         captured by their doc comments.`
       - `No CONTEXT.md for this package: it wraps an external system's primitives rather than
         introducing internal domain concepts.`
       - `No CONTEXT.md for this package: it exposes thin value types and driver abstractions over
         external systems rather than internal domain concepts.`

   ## Package scope
   <Which product context, support layer, or shared kernel this package belongs to.>

   ## Core concept owned
   <One sentence stating what this package is the canonical home for. Other packages must
   extend or reuse this rather than reimplement.>

   ## Responsibilities
   - Owns: <bullet list of what lives here. Include capabilities that lack a documented type
     if the code clearly implements them — colour handling, TTY detection, file tailing, etc.>
   - Does **not** own: <bullet list of nearby concerns and the package that owns them. This is
     the most valuable section — it prevents drift.>

   ## Upstream (this package depends on)
   - `<pkg>` — <role it plays for us>

   ## Downstream (consumers of this package)
   - `<pkg>` — <how they use us>

   ## Invariants & conventions
   - <Package-specific rules: error shape, statelessness, abort/panic conventions, exit-code
     conventions, file-layout contracts, concurrency contracts, etc. Derive these from the code,
     not from generic templates.>

   ## When developing in this package
   - [ ] <Tailored question that catches the most likely drift in this package.>

   ## See also
   - <Optional. Add citations only for documents that exist in the repo and corroborate the
     charter — e.g. an auxiliary conceptual index, an architecture doc, or a sibling package's
     PACKAGE.md. Omit the section entirely if there is nothing real to cite.>
   ```

   The checklist must be **tailored**, not generic. Look at what could go wrong specifically for this
   package and write the checklist question that catches it. Read the project's coding-conventions
   document (e.g. `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `STYLE.md`, `docs/conventions.md` —
   whichever exists) and surface any rule that this package can plausibly violate. Typical categories
   (translate to the host language as appropriate):
    - Code-organisation gates (e.g. "if behaviour would naturally be a method on a project type, did I
      make it one?" for OO/method-oriented projects; "did I use a free function rather than smuggling
      state through a closure?" for functional projects).
    - Error-shape contract (does any new error implement the project's user-facing failure type /
      interface / hierarchy, if there is one?).
    - Output discipline (are writes routed through injected writers/loggers rather than ambient I/O
      like `stdout`/`stderr`/`console.log`/`print()`, if the project has that rule?).
    - Naming bans (e.g. reserved terms in this project's vocabulary).
    - "Did I preserve <invariant>?" for any documented invariant in this package.
    - "Did I run <regen command>?" for any generated index or artefact this project maintains.

4. **Single-concept smell test → Clean-concept rating**

   Every charter gets a `Clean-concept rating` section. This step decides whether it is the short pass
   form or the detailed failing form.

   a. **The "and" rule.** Read the draft `Core concept owned` sentence and the `Owns` bullets together.
      Count meaningful coordinating `and`s — those joining distinct *concerns* (not stylistic
      conjunctions inside a single concern, and not "X and Y" where Y is a trivial qualifier of X).

        - 0 or 1 meaningful `and` → the package is plausibly single-concept; write the **short pass
          form** described in (c) and skip (b).
        - **2 or more meaningful `and`s, or the `Owns` list spans more than 3 distinct capability
          areas** → the package fails the smell test. Continue to (b) and write the **detailed form**.

      Also trigger the rating if **any** of the following is true:
        - package- or module-level mutable state exists (other than tables of constants / frozen
          lookup data);
        - a `// not good`, `// TODO`, `// hack`, `# FIXME`, or similar self-admission comment exists in
          the code;
        - the user's prior PACKAGE.md annotation says the package is "unclear" or "to be split";
        - the package mixes the project's typed/structured errors with bare aborts (panics / throws /
          asserts used for programmer errors) in an inconsistent way (worth a note even when the
          package is otherwise single-concept).

   b. **Ask and answer the rating question.** On a 1–10 scale, how cleanly does this package own a
      single concept? Use this rubric:

        - **9–10** — One sentence states the owned concept; the language's type system or contracts
          mechanically prevent domain drift; the "Does not own" list is rich and specific; no globals;
          no dead state; no package-vocabulary leaks; presentation lives elsewhere.
        - **7–8** — Single concept, but with one or two specific layer-leaks (e.g. user-facing error
          vocabulary that assumes one caller's domain; a presentation helper that should live elsewhere;
          a dead/unused field).
        - **5–6** — Two related concerns under one package; "Does not own" thins out; one or two
          globals; mixed error discipline; otherwise coherent.
        - **3–4** — Three or more unrelated concerns; no single owned concept; package assembled by
          adjacency, not concept; package-level mutable state.
        - **1–2** — Pure "utils" / "helpers" / "common" sink with no claim to a concept.

      The model writing the PACKAGE.md must produce an **explicit numeric score**, not a range. Pick
      the single best number and justify it.

   c. **Add the `Clean-concept rating` section** at the bottom of the PACKAGE.md, after `See also` (and
      after any pre-existing `Additional notes`).

      **Short pass form** (when the package passed the smell test in (a)):

      ```markdown
      ## Clean-concept rating — PASS

      <One short paragraph — two or three sentences — stating that the package owns a single concept
      cleanly, naming that concept, and noting the smell-test signal that confirmed it (e.g. "single
      owned concept, no package-level mutable state, no self-admission comments").>
      ```

      **Detailed form** (when the package failed the smell test in (a) and a numeric score was assigned
      in (b)):

      ```markdown
      ## Clean-concept rating — N/10

      A reviewer assessment of how cleanly this package owns a single concept. Captured here so the
      next reader sees the known design debt up front; revisit when any of the items below is
      addressed.

      <One short paragraph summarising the verdict.>

      **Strengths** (omit if rating < 5)
      - <Specific, citation-style bullets — name the type / file that demonstrates each strength.>

      **What costs the points**
      1. <Specific issue with a file/line or type citation, plus the concrete fix.>
      2. <...>

      **Path to N+1 (or N+2)**: <concrete steps that would lift the score. For low scores, describe the
      split into proposed sibling packages by name.>
      ```

      Be concrete. "Mixed concerns" is not a finding; "OutputFormat enum, colour helpers, TTY
      detection, and file tailing each have different lifecycles" is.

5. **Write and verify (per package)**

   For each package in the resolved set:

   a. Write the charter to `<package-dir>/PACKAGE.md`. Follow project rules for added files.

   b. Re-read what was written. Verify:
        - every section heading from Step 3 is present and in order;
        - every line ≤ 120 characters;
        - every claim about a type, function, or behaviour can be traced to the package code read in
          Step 2 (auxiliary references may corroborate, but the code is authoritative);
        - the upstream list matches the actual dependencies of the package (imports / uses / requires /
          manifest-declared);
        - the downstream list matches actual repo-wide search results;
        - the `Clean-concept rating` section is present; if it is the detailed form, the score is a
          single integer and every "costs the points" bullet cites a specific code location or type; if
          it is the short pass form, it is a single short paragraph with no score;
        - any hand-written section earmarked in Step 1e (e.g. `## Additional notes`) survives intact
          above the `Clean-concept rating` section.

   c. Record the per-package facts you will need for the batch summary in Step 7: owned concept (one
      line), Owns count, Does-not-own count, upstream count, downstream count, Clean-concept rating
      ("PASS" for the short form, or the numeric score for the detailed form).

   Progress reporting: for sets larger than ~10 packages, emit a one-line status message between
   packages so the user can see progress (e.g. `[7/32] src/workspace/image — rated 7/10`). Do not print
   the full per-package summary block until Step 7.

6. **Cross-package consistency check**

   Run once after every charter has been written. The goal is to catch the kinds of drift that only
   surface when several charters are compared side-by-side.

   a. **Reciprocity of upstream / downstream.** For every charter A that lists B as an upstream
      dependency, the charter for B (if present in this batch) must list A as a downstream consumer,
      and vice versa. Build the bidirectional graph from the charters and report any one-sided edges.
      Fix the affected charters in place.

   b. **No orphan cross-references.** Every package name mentioned in a "Does not own" line that points
      to another package in the batch must resolve to a real directory in the set or in the repo. Flag
      any unresolved citation.

   c. **Glossary section consistency.** Every charter must have exactly one `## Glossary` section that
      matches one of the three forms in Step 3. Flag any charter that retains a `## Ubiquitous
      language` section, defines terms inline, or omits the Glossary entirely. Cross-context vocabulary
      collisions (the same term meaning different things in different contexts) belong in the project's
      `CONTEXT-MAP.md`, not in any individual `PACKAGE.md`.

   d. **Rating distribution sanity.** If more than half the batch is rated < 5, double-check the
      rubric was applied honestly; mass-low ratings are more likely a rubric calibration problem than a
      codebase-wide failure.

   Do not rewrite charters wholesale during this pass — only the specific lines flagged above. If a
   flagged issue cannot be fixed by a small in-place edit, surface it as an open question in the Step 7
   summary.

7. **Batch summary**

   Show the user a single aggregated summary after all charters are written and the consistency pass
   has run:

   ```
   ✅ <N> PACKAGE.md charters written.

   📋 Per-package ratings (sorted worst-first):

   | Package                                  | Rating   | Owned concept                           |
   |------------------------------------------|----------|-----------------------------------------|
   | <pkg path>                               | <N/10>   | <one-line owned concept>                |
   | <pkg path>                               | PASS     | <one-line owned concept>                |
   | ...                                      |          |                                         |

   🔍 Consistency findings:
   - <One bullet per cross-package issue caught in Step 6, with the affected packages.
     "None" if the pass was clean.>

   📝 Charters needing follow-up: <list of packages rated < 7, or "none">.
   ```

   Sort the ratings table worst-first so the packages most in need of attention sit at the top. `PASS`
   (single-concept packages) sort below all numeric ratings.

8. **Offer next steps**

   If one or more packages were rated < 7, ask once for the whole batch:

   > "<count> package(s) failed the single-concept smell test (<list>). Would you like me to draft a
   > split proposal (new package names, what moves where, migration steps) as a plan under the
   > project's plans directory (e.g. `docs/llm/plans/`, `docs/plans/`, or wherever this project keeps
   > them)? I can produce one plan covering all of them, or one plan per package — your call."

   Do not produce any plan unless the user says yes and chooses a granularity.

**Output**

One `PACKAGE.md` written per target package directory, conforming to the structure above. Every charter
ends with a `Clean-concept rating` section: a short `PASS` paragraph when the package is single-concept,
or `Clean-concept rating — N/10` with concrete, citation-style findings when it fails the smell test.
After the per-package writes, a single aggregated batch summary and consistency report is shown to the
user.

**Guardrails**

- Do NOT proceed without the package code being read in full — no auxiliary index, doc-comment summary,
  or prior charter substitutes for actually reading the source. The code is what reveals globals, abort
  sites, hidden helpers, dead state, and capabilities lacking a documented type. **This applies to every
  package in the batch.** Do not skim or compress later packages once the pattern feels familiar.
- Do NOT short-circuit the per-package read by inferring one package's content from another's. Each
  package gets its own full read; "looks similar to the previous one" is precisely how drift and missed
  smells creep in.
- Do NOT generate generic checklist items; tailor `When developing in this package` to what is actually
  risky in this package and to this project's coding conventions.
- Do NOT omit the `Clean-concept rating` section. Single-concept packages get the short `PASS` form (a
  single paragraph, no score); packages that fail the smell test get the detailed form with a numeric
  score and citation-style findings.
- Do NOT soften a low rating. If a package fails the smell test, say so plainly with a numeric score
  and specific findings. Vague ratings ("medium") and missing scores are worse than honest low scores.
  The batch summary's worst-first sort exists to keep this visible.
- Do NOT mix presentation concerns into a primitive's `Owns` list without flagging it as a cost in the
  rating section.
- Do NOT overwrite a hand-written annotation (e.g. `## Additional notes`) — preserve it above the rating
  section.
- Do NOT invent a `## See also` reference that does not exist. Cite only documents you verified during
  Step 2; omit the section entirely if there is nothing real to cite.
- Do NOT skip the cross-package consistency pass (Step 6). It is the only step that catches one-sided
  upstream/downstream edges and Glossary-section regressions, and it cannot be performed at all on a
  single-package invocation. Run it whenever the batch contains two or more packages.
- Do NOT ask per-package follow-up questions during the batch — collect everything for Step 8's single
  offer.
- Do NOT assume a particular language's conventions. Translate every mention of file extensions, error
  types, ambient-I/O calls, abort mechanisms, manifest files, and visibility rules to the host project's
  equivalent before applying.
- Hard-wrap every line at 120 characters. Match the spelling convention of the surrounding project
  documentation (check the project's conventions document if unsure).

**Integration with project conventions**

This skill implements a package-charter expectation that projects typically encode in their
coding-conventions document (e.g. `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `STYLE.md`). The typical
rule reads something like:

> Touch-check the package `PACKAGE.md` when changing a package's surface and update it if the package
> scope, glossary reference, owned concept, or "does not own" list no longer matches reality.

If your project's conventions document has no such rule, this skill still produces useful output — but
consider adding the rule so that charters stay in sync with the code over time.

It is intended for three situations, with batch as the default:

1. **Bulk bootstrapping** — generating charters for a whole subtree (or `--all`) that does not yet have
   them. The cross-package consistency pass in Step 6 is critical here; the value of the batch is
   consistency across the set, not just N separate documents.
2. **Subtree refresh** — regenerating charters after a non-trivial surface change that crosses package
   boundaries. Refresh mode reads the existing charters first (Step 1e) and preserves hand-written
   sections.
3. **Single-package bootstrapping or refresh** — the degenerate case, with the same per-package rules
   as the batch. The cross-package consistency pass is skipped when only one package is in scope.
