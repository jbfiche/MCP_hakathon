# Inventory

What already exists, so that on Day 2 nobody spends the morning rebuilding a UniProt client.

| File | Contents |
| --- | --- |
| [`mcp-servers.md`](mcp-servers.md) | MCP servers relevant to cancer systems biology |
| [`skills.md`](skills.md) | Agent Skills — the *other* way to drive an LLM-based agent |
| [`resources-to-wrap.md`](resources-to-wrap.md) | Databases, tools and models that have **no** server yet |

## The rule for what goes in here

Every entry carries a **status**:

- **confirmed** — an organiser has used it or vouches for it, or it is published by the
  organisation that owns the underlying data.
- **candidate** — found by search, plausible, **not yet vouched for**. Do not present a candidate
  to participants as a recommendation until an organiser has moved it to confirmed.

This is deliberate. There are thousands of MCP servers on GitHub and most of them are a thin,
unmaintained wrapper generated in an afternoon. We recommend a server only when we know it, or
when it is official. Everything else is listed so you know it exists, not because we endorse it.

*Organisers: `candidate` rows are yours to promote or delete.*

## What the sweep found, and did not

A search of the official [MCP Registry](https://registry.modelcontextprotocol.io) for `cancer`,
`genomics`, `bioinformatics` and `biology` (September 2026) returned almost nothing usable for
this field: a handful of single-vendor servers, one plant-genomics server published 12 times, and
no cancer systems-biology entry beyond what is already listed here. **The gap this hackathon is
aiming at is real.** If your group builds something good, publishing it to the registry is a
genuine contribution, not a formality.
