# demo-resource

No tools. One **resource** (`genes://panel`, a JSON document) and one **resource template**
(`genes://panel/{symbol}`, one line of text per gene). A resource is data the *application*
decides to load into the model's context, addressed by a URI; the model does not call it
the way it calls a tool.

The syntax is in [`resource_server.py`](resource_server.py): `@mcp.resource(uri, mime_type=...)`
on a function. A `{placeholder}` in the URI makes it a template, and the placeholder must
match a parameter name. Unknown URIs raise `ResourceError`.

## Try it in your agent

Install the plugin (see the [repository README](../../README.md#install-the-demo-plugins)).
Then find where your host lists MCP resources:

- **Claude Code**: type `@` in the prompt and look for `demo-resource:genes://panel`; the
  content is attached to your message. Or ask: *"Read the resource genes://panel/KRAS from
  the demo-resource server."*
- **VS Code**: the **Add Context** menu lists MCP resources.
- **Codex**: check whether resources appear at all; hosts differ, and that is the finding.

## Run and test it by hand

```bash
cd plugins/demo-resource
uv run --with "mcp[cli]" mcp dev resource_server.py   # the Resources tab in the Inspector
```

```bash
uv run pytest plugins/demo-resource
```
