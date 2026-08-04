---
name: roundtable-review
description: Runs a multi-perspective critique and synthesis pass over a plan, spec, or architecture proposal. Use when 
  the user asks for a roundtable, swarm, council, adversarial review, downstream impact check, or specialist feedback 
  before implementation.
---

# Roundtable Review

Use this before implementation when a plan needs sharper product, architecture,
operations, or downstream-impact thinking.

## Workflow

1. Establish the proposal under review.
    - Read the current spec, plan, branch diff, and relevant code/docs.
    - If the user requested external inspiration or current product behavior,
      browse primary/current sources and record the links.
    - State the assumptions that are already settled so reviewers do not
      relitigate them.

2. Assign specialist seats.
   Use separate agents when available; otherwise run the perspectives as
   distinct passes yourself. Pick only seats that fit the problem.
    - Codebase Consistency: existing patterns, ownership boundaries, naming,
      generated files, package seams.
    - Simplifier: tables, states, abstractions, and duplicate concepts that can
      collapse without losing behavior.
    - Product/UX: labels, trust, empty/loading/error states, editor versus public
      surfaces, user expectations.
    - Reliability/Operations: queues, retries, idempotency, leases, observability,
      cost, support/debug flows.
    - Data/SQL: schema shape, constraints, indexes, migrations, query plans,
      deletion semantics.
    - Prompt/AI: task framing, structured output, validation, repair, protected
      tokens, privacy/logging.
    - SEO/External Research: current market behavior, search/indexing risk,
      standards, policy constraints.
    - Downstream Integrations: copied data, caches, APIs, analytics, admin tools,
      worker bindings.

3. Run independent critiques.
   Each seat should produce:
    - strongest concern;
    - concrete downstream impact;
    - recommended change;
    - confidence level;
    - evidence or file/source references.

4. Commune at the roundtable.
   Synthesize, do not concatenate. Group critique into:
    - accept now;
    - accept with narrower scope;
    - defer explicitly;
    - reject, with reason.
      Prefer changes that remove ambiguity, prevent misleading UX, or make failure
      modes observable. Do not let speculative elegance overrule settled product
      constraints.

5. Pursue promising threads.
   If one critique is high-leverage but under-evidenced, do a focused code or
   web exploration before final synthesis. If a critique is weak, dismiss it
   plainly.

6. Patch the artifact.
   Update the spec/plan so accepted decisions are encoded where future
   implementers will see them. Then scan for stale contradictions and report
   what changed.

## Output Shape

Keep the final answer short:

- what the roundtable changed;
- which critiques were rejected or scoped down;
- validation or contradiction scans performed;
- links to updated files and external references, when used.