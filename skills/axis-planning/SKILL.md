---
name: axis-planning
description: Convert an issue, prompt, story, prototype, or free-form description into an
axis CLI plan that matches codebase conventions and quality requirements.
Use when the user says "plan", asks to create or edit files in docs/llm/plans/, wants to
finalise a plan, run the OF gate or new-types gate, or move a completed plan.
argument-hint: "the context being discussed, a file describing what needs to be done, or a free-form description"
---

# Axis Planning

## Bundled assets

- Markdown template: `templates/plan.md.template`
- HTML template: `templates/plan.template.html`
- Shared review CSS: `assets/css/base.css`

When generating HTML in the target repo, ensure `assets/css/base.css` exists at the
review-surface root. If missing, create it from the bundled CSS so the HTML can load
`../../assets/css/base.css`.

## Output

Produce a paired Markdown + HTML plan:

- Concise Markdown plan in `docs/llm/plans/`.
- Paired HTML review surface.
- Steps sized as small, independently verifiable vertical slices.
- Explicit `Risks` section.
- Mermaid `classDiagram` in the HTML, with visual highlighting for added, changed, risky,
  or uncertain elements.
- HTML sections stack vertically; do not use side-by-side layout unless comparing exactly
  two alternatives.

## Before writing a plan

Read before drafting:

1. **`CONTEXT.md`** — adopt its terminology exactly; do not invent synonyms.
2. **`docs/llm/package-index.md`** — identify in-scope packages.
3. **`internal/<package>/PACKAGE.md`** for every touched package — understand
   responsibilities, boundaries, and invariants before deciding where code lives.
4. **`docs/llm/responsibility-map.md`** and **`docs/llm/type-index.md`** — check for existing
   types before introducing new ones.
5. **`docs/specs/*`** — only when the plan changes narrative or results output to
   stdout/stderr.

If code or responsibilities appear to live in the wrong package (relative to its
`PACKAGE.md` charter), **stop and ask the user** before incorporating it into the plan.

## Plan structure

### 1. Overview

One concise paragraph stating what changes and why. Do not duplicate the input.

### 2. Concept diagram

Mermaid `classDiagram` showing affected types and interfaces only.

- Structs and datatypes map to diagram classes.
- Highlight added, changed, risky, or uncertain elements visually.

### 3. Steps

Each step is a small vertical slice that can be verified independently. Each step must contain:

- **What** — the change.
- **Where** — package and file, justified against the relevant `PACKAGE.md`.
- **Corner cases** — edge conditions and failure modes to handle and test (zero values,
  empty collections, concurrent access, missing dependencies, error propagation,
  boundary inputs).

### 4. Risks

Distinct section. List open risks, uncertainties, and feedback still affecting implementation.

### 5. Test plan

Test cases that must exist after implementation, grouped by file. At least one case per
corner case listed in the steps.

### 6. Commit message

Conventional commit header + one concise paragraph body.

## Quality gates — mandatory before finalising

### OF gate

Scan every `func` signature. For each `func foo(x *ProjectType, ...)`:

1. Should this be a method on `*ProjectType`?
2. If yes — rewrite as a method.
3. If it must stay standalone, justify inline: constructor, cross-package boundary, or
   pure primitive helper.

Standalone functions over project-defined types are a code smell. Resolve before finalising.

### New-types gate

Any new `struct`, `interface`, or named function type must:

- Be checked against `docs/llm/responsibility-map.md` — does an existing type already own
  this concept?
- Include a full godoc block using the template at `docs/llm/type-doc-template.md`.
- Use behaviour-oriented or role-based names (e.g. `ImageBuilder`, `RepositoryInspector`).
  Avoid `Driver`, `Handler`, `Manager`.

## Last step in a plan

The final instruction in the plan body is to move the plan file to
`docs/llm/plans/completed/` using `git mv` as part of the same change set. If the file
is not yet in the git index, `git add` it first.

## Language

- UK English spelling throughout.
- Use the exact terms from `CONTEXT.md`; do not introduce synonyms.
- Avoid "canonical" unless multiple competing instances exist and exactly one is authoritative.
