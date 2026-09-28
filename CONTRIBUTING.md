# Contributing

## Commit convention

This repository is not published anywhere (`pyproject.toml` sets `tool.uv.package = false`), so there
is no release-automation or changelog machinery here, and none is planned unless that changes. The
convention below exists purely to keep the commit history readable for whoever reads it next —
human or agent — not to drive an automated version bump.

Format:

```
type(scope): summary

[optional body — favor writing one; the reasoning behind a change rarely fits in one line]
```

- `scope` is mandatory and names the topic the commit is about (see below) — not the action, not the
  layer.
- Imperative mood, lowercase after the colon, no trailing period, subject line kept short (aim for
  ≤72 characters).
- Add a body whenever the *why* — the reasoning, trade-off, or context — doesn't fit in the subject.

### Allowed types

| Type | Use for |
|---|---|
| `feat` | New capability or teaching content — a new pattern, a new skill, a new inventory entry |
| `fix` | Correcting an error in existing content or code |
| `docs` | Plain documentation changes (`README.md`, `docs/`, `inventory/`) not covered by `report`/`design`/`rdm` below |
| `chore` | Tooling, config, dependency, or repo-scaffolding changes with no content/behavior change |
| `refactor` | Restructuring without changing behavior or content |
| `test` | Adding or changing tests |
| `report` | Documents produced under the `writing-reports` skill, filed under `__reports__/` — findings, observation, notice, open-question, architecture, test-definition, knowledge-transfer. Not plain documentation: these follow that skill's own model-first, stakeholder-reviewable contract. |
| `design` | Durable design or architecture decisions, filed under `__design__/` or produced by a design-canon skill. Not plain documentation: these are decisions, not descriptions. |
| `rdm` | Roadmap documents produced under the `managing-roadmaps` skill, filed under `__roadmap__/<campaign>/` |

There is no fixed scope list. Name the scope after the repo area or topic the commit is about — e.g.
`patterns`, `docs`, `inventory`, `skills`, `plugin`, or a specific report topic like
`mcp-python-sdk-conformance`. Keep related commits on the same scope so the history reads as one
coherent narrative per topic; a scope change signals a deliberate shift in focus.

### No linting, no blocking hooks

Enforcement is advisory, not mechanical: no commitlint config, no pre-commit hook rejecting a
message. Commits come from both event organizers/participants and Claude agent sessions, and a
blocking local hook risks rejecting a valid but unconventionally-phrased agent commit. If that
changes — e.g. this repo starts publishing something — revisit this file and consider adding
automation at that point, per the writing-history skill's `convention-setup` flow.

---
*Established 2026-09-10 via the writing-history skill's setup interview.*
