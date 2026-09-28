# demo-progress

One slow **tool**, `count_to`, that waits one second per step (ten steps by default) and
reports progress after each one. It shows two things in [`progress_server.py`](progress_server.py):

- how a tool gets the per-request `Context` — annotate any parameter with `Context`; the host
  never sees it in the input schema;
- `await ctx.report_progress(progress, total, message)`, which sends one MCP progress
  notification per step.

## Try it in your agent

Install the plugin (see the [repository README](../../README.md#install-the-demo-plugins)),
then ask:

> Use the demo-progress server to count to 10.

What you should see depends on the host, and that is the point of the demo: some hosts
render the progress messages live (`step 3 of 10`), some show a spinner, some show nothing
until the ten seconds are over. Ask for `count_to` with `n=3, delay=0` if you only want to
check that the tool works.

The test file shows the client side of the same feature: pass `progress_callback=` to
`call_tool` and every notification lands in your function.

## Run and test it by hand

```bash
cd plugins/demo-progress
uv run --with "mcp[cli]" mcp dev progress_server.py
```

```bash
uv run pytest plugins/demo-progress
```
