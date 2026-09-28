# demo-elicitation

One **tool**, `greet`, that has no arguments the model can fill: the server asks *you* for
your name, waits for the answer, and then greets you. That round-trip is **elicitation**.

The syntax is in [`elicitation_server.py`](elicitation_server.py). Three pieces:

1. a Pydantic model for the form (`Name`), flat primitive fields only;
2. a *resolver* function that returns `Elicit(message, Name)`;
3. a tool parameter annotated `Annotated[ElicitationResult[Name], Resolve(ask_name)]`. The
   SDK fills it with the outcome, and the tool `match`es on accept, decline or cancel.

Why a resolver rather than `await ctx.elicit(...)`: the 2026-07-28 protocol revision has no
server-initiated requests, so the question travels back inside the tool result and the host
retries the call with the answer. The resolver form works on both old and new connections;
the `ctx.elicit()` form only on old ones.

If your tool simply cannot proceed without the answer, annotate the parameter as
`Annotated[Name, Resolve(ask_name)]` instead: you get the model directly, and a decline or
cancel aborts the call with a tool error.

## Try it in your agent

Install the plugin (see the [repository README](../../README.md#install-the-demo-plugins)),
then ask:

> Use the demo-elicitation server to greet me.

One of three things happens, and finding out which is the purpose of this demo:

- the host shows a form or a question, you type a name, the agent says `Hello, <name>!`;
- the host supports elicitation but you decline: `No name given. Hello, stranger!`;
- the host does not support form elicitation: the call fails with an MCP error saying the
  client did not declare the `form elicitation` capability. That is the server being honest
  rather than guessing.

The test file drives all three outcomes with the SDK's own client and its
`elicitation_callback=`.

## Run and test it by hand

```bash
cd plugins/demo-elicitation
uv run --with "mcp[cli]" mcp dev elicitation_server.py
```

```bash
uv run pytest plugins/demo-elicitation
```
