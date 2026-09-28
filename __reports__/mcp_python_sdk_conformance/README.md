# MCP Python SDK v2 Conformance

Audit of the Model Context Protocol Python SDK v2 against the 2026-07-28 specification revision — what the SDK actually implements (code/doc evidence), not what it claims. Compiled from five parallel research agents, one per spec domain (base protocol/lifecycle, transports/utilities, server features, client features, authorization/security). Rust SDK deliberately excluded from this round.

## Documents

### Round 00

- [00-findings_v0.md](00-findings_v0.md) — **latest**. Headline result (68.7% full conformance), per-domain breakdown, the eight flagged items that matter most for a build decision, and steering questions.

## Status

- Full conformance rate: **68.7%** (46/67 audited features)
- One confirmed real gap: async/long-running tool execution (Tasks extension) — types defined, no wire handlers.
- Weakest area: the Security Best Practices document layered on top of OAuth (authorization mechanics themselves are solid).
- Open item carried to next round: reconcile the apparent default-protocol-version disagreement between `ClientSession.initialize()` and the high-level `Client` wrapper — needs a direct source read, not just docs.
- Decision required from the team: whether the hackathon build needs long-running tool execution or third-party token proxying — both are the SDK's weak points and only matter if the build touches them.

Interactive matrix (source of truth for individual rows): https://claude.ai/code/artifact/9f0a7e5b-c218-4eee-b765-d7b752741e50 — local copy at [mcp-python-sdk-matrix.html](mcp-python-sdk-matrix.html)
