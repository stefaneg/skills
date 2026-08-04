---
name: in-development-planning
description: Convert an issue, story, analysis or prototype into a plan that matches codebase conventions and 
  quality requirements.
argument-hint: "@reviewed-story.md and @reviewed-story.html"
---

# Planning Skill

## Bundled review assets

- Plan Markdown template: `templates/plan.md.template`
- Plan HTML template: `templates/plan.template.html`
- Shared review CSS: `assets/css/base.css`

When generating HTML in a target repo, ensure `assets/css/base.css` exists. If it does not, create it from the 
bundled shared review CSS so generated HTML can load `../../assets/css/base.css`.

## Output

Produce:

- a concise Markdown plan with implementation steps.
- a paired HTML review surface
- small vertical slices
- explicit risks
- a Mermaid `classDiagram` in HTML

## Rules

- Do not duplicate the input - create a concise, one paragraph summary.
- Keep steps concrete and short.
- Carry forward open feedback that still affects implementation.
- Prefer slices that can be verified independently.
- The HTML should make sequencing, risks, and remaining uncertainties easy to critique.
- Plans must always include a Mermaid `classDiagram`.
- Structs and datatypes map to diagram classes.
- Use visual highlighting in the diagram to show added, changed, risky, or uncertain elements.
- Plan sections in HTML should normally stack vertically; do not use side-by-side layout unless comparing exactly two 
  alternatives.
