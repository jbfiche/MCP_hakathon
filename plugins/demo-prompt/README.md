# demo-prompt

No tools. One **prompt**, `summarise_gene`, with one argument. A prompt is a canned request
that a *person* picks from the host's menu; the model never decides to use one. Compare it
with a tool (the model decides) and a resource (the application decides).

The syntax is in [`prompt_server.py`](prompt_server.py): `@mcp.prompt(title=...)` on a
function whose parameters become the prompt's arguments and whose return value is the text
of the request. Return a `list[Message]` instead of a `str` to seed a multi-turn
conversation.

## Try it in your agent

Install the plugin (see the [repository README](../../README.md#install-the-demo-plugins)).
Then look for the prompt where your host lists MCP prompts:

- **Claude Code**: type `/` and look for `demo-prompt:summarise_gene`, then pass `TP53`
  as the argument, e.g. `/demo-prompt:summarise_gene TP53`.
- **VS Code**: type `/` in the chat box; MCP prompts are listed with the server name.
- **Codex**: check the prompts or slash-command list once the plugin is installed.

If you cannot find it, that is a finding too: not every host exposes prompts, and this
plugin is the quickest way to check yours.

## Run and test it by hand

```bash
cd plugins/demo-prompt
uv run --with "mcp[cli]" mcp dev prompt_server.py   # the Prompts tab in the Inspector
```

```bash
uv run pytest plugins/demo-prompt
```
