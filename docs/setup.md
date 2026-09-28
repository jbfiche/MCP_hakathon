# Setup — before you arrive

Work through this before Day 1. It takes about twenty minutes, and the point of doing it early is
that if something breaks, you find out now rather than at 09:15 on Friday.

The call for participation lists four prerequisites. This page covers the first two.

## 1. Python, via uv

You need Python 3.10 or newer. The materials use [uv](https://docs.astral.sh/uv/), which manages
both Python versions and dependencies, so you do not need to have a working Python already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS, Linux
```

On Windows, use the PowerShell installer from the uv documentation, or run everything under WSL.

Check it:

```bash
uv --version
```

If your institute manages your Python through conda or a module system and you would rather not
add uv, everything here also works with `pip install "mcp[cli]"` in a virtual environment on
Python 3.10+. The plugin READMEs give the `uv` command because it is one line and needs no
pre-existing environment; substitute your own if you prefer.

## 2. An LLM agent

You are responsible for your own agent access and any usage costs. Any of these works:

- **Claude Code**, OpenAI **Codex**, **Mistral Vibe**, **OpenCode**
- **VS Code** with an LLM extension

**Academic participants: GitHub Copilot Pro is free for academic staff and students worldwide**,
works inside VS Code, and is entirely sufficient for this hackathon. If you do not already pay
for an agent, use this.

- Students: <https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/enable-copilot/set-up-for-students>
- Teachers and OS maintainers: <https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/enable-copilot/set-up-for-teachers-and-os-maintainers>

Whichever you pick, confirm before the event that **you can add an MCP server to it**. Every host
has its own configuration file or command for this, and finding it is the single most common
first-hour blocker.

## 3. Check that it all works

Clone the repository and run one server:

```bash
git clone https://github.com/sysbio-curie/MCP_Hackaton.git
cd MCP_Hackaton
uv sync
uv run pytest
```

18 tests should pass. Then look at a server by hand:

```bash
cd plugins/demo-tools
uv run --with "mcp[cli]" mcp dev tools_server.py
```

This opens the **MCP Inspector** in your browser: a client that shows you a server's tools,
resources and prompts, and lets you call them. Go to the **Tools** tab and call `add` with
`a=2, b=3`. If you see `5`, your environment is ready.

Finally, install the demo plugins into your own agent — the instructions are in the
[README](../README.md#install-the-demo-plugins) — or check that every plugin's server starts
without installing anything:

```bash
uv run python scripts/check_servers.py
```

## 4. Bring a question

The most useful thing you can bring is not software. It is **one concrete thing you do by hand
that you wish an agent could do**: a lookup you repeat, a file format you keep converting, a
model you want to interrogate conversationally, a pipeline whose outputs you keep re-reading.

Groups are assigned from the topic of interest you gave in the application form. The projects
that go well on Day 2 are the ones where somebody at the table already knows what question they
want answered — see the three criteria in
[`inventory/resources-to-wrap.md`](../inventory/resources-to-wrap.md).

## If you get stuck

Two one-hour online sessions are scheduled the week before the event, specifically for setup
questions. Bring the error message.
