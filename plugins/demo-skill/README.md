# demo-skill

The Agent Skills syntax, shown once: one skill, `authoring-an-mcp-server`, a guide to writing
an MCP server with the MCP Python SDK v2. No MCP server of its own.

The whole syntax is in
[`skills/authoring-an-mcp-server/SKILL.md`](skills/authoring-an-mcp-server/SKILL.md): a
`skills/<name>/SKILL.md` with YAML front matter (`name` must equal the directory name,
`description` says when the agent should load it) and an optional `references/` folder for
depth — here,
[`references/sdk-v2-cheatsheet.md`](skills/authoring-an-mcp-server/references/sdk-v2-cheatsheet.md).

## Try it in your agent

Install the plugin (see the [repository README](../../README.md#install-the-demo-plugins)),
then ask:

> Help me write an MCP server for my own analysis.

Watch whether the host loads the skill. Claude Code lists it as
`demo-skill:authoring-an-mcp-server`; other hosts differ, and that is the finding.

## Run and test it by hand

There is no server to run. `uv run pytest tests` checks the skill's front matter as part of
the plugin structure test.
