# Agent Skills

MCP is not the only way to extend an LLM-based agent, and for a lot of research work it is not
the best one. **Agent Skills** are the other half of the story, and this hackathon covers both.

## The distinction that matters

| | MCP server | Agent Skill |
| --- | --- | --- |
| **What it is** | a running process speaking a protocol | a folder with a `SKILL.md` in it |
| **What it adds** | new *capabilities* — code the agent can call | new *procedure* — instructions the agent follows |
| **Written in** | Python, TypeScript, anything | Markdown (plus optional scripts) |
| **Use when** | the agent needs to reach a database, run a simulation, touch a file system | the agent needs to know *how your lab does something* |
| **Cost to write** | an afternoon | twenty minutes |

The rule of thumb: **if the agent lacks an ability, write a server. If it lacks knowledge or
discipline, write a skill.**

"Query our cohort database" is a server. "Our QC thresholds, and the order we apply them, and the
three things we always check before trusting a differential-expression result" is a skill. Most
real research workflows need one of each, and the skill is usually the one that makes the
difference — because the failure mode of an agent on a research task is rarely a missing tool,
it is doing the right steps in the wrong order.

Skills are specified openly at <https://agentskills.io/specification>: `name` and `description`
in YAML frontmatter are the only required fields, plus optional `scripts/`, `references/` and
`assets/` directories. An agent loads only the `name` and `description` at startup and pulls in
the body when the task calls for it, so a skill costs almost nothing until it is relevant.

This repo ships one:
[`plugins/demo-skill/skills/authoring-an-mcp-server/`](../plugins/demo-skill/skills/authoring-an-mcp-server/),
which ships as the `demo-skill` plugin. Read it as a worked example of the format — it is what
you will write on Day 2 alongside your server.

## Collections

### Anthropic Life Sciences skills

**Status: confirmed.** In <https://github.com/anthropics/life-sciences> (see
[`mcp-servers.md`](mcp-servers.md)). Six skills, of which these are the ones a cancer group would
actually use:

| Skill | What it encodes |
| --- | --- |
| `single-cell-rna-qc` | quality control for scRNA-seq following scverse best practices |
| `scvi-tools` | deep-learning single-cell analysis with scvi-tools |
| `nextflow-development` | running nf-core pipelines (rnaseq, sarek, atacseq) on local or GEO/SRA data |
| `clinical-trial-protocol` | generating FDA/NIH-compliant trial protocols |
| `instrument-data-to-allotrope` | converting instrument output to the Allotrope Simple Model |
| `scientific-problem-selection` | Fischbach & Walsh framework for choosing what to work on |

`nextflow-development` and `single-cell-rna-qc` are the clearest demonstration of the point
above: neither adds a capability the agent lacked. They add *method*.

### Scientific Agent Skills (K-Dense)

**Status: candidate — needs disambiguation.** Two related artefacts exist under this name, and
we should be explicit about which one we recommend:

- <https://github.com/K-Dense-AI/scientific-agent-skills> — a large library of scientific skills
  (advertised as 165 skills plus 100+ database references) covering biology, chemistry, medicine
  and drug discovery, compatible with the open Agent Skills standard.
- <https://github.com/K-Dense-AI/claude-skills-mcp> — an MCP server that searches and retrieves
  those skills by vector search. A neat illustration of the two mechanisms composing: a server
  whose job is to find the right skill.

*Organisers: which of these is "Claude Scientific Skills" as you use it? A third possibility is
a locally configured `scientific-skills` server, which is what Eliott has in his own MCP
configuration. Naming it precisely matters here, because the size of that library is exactly the
kind of thing participants will install without reading.*

## Writing one during the hackathon

If your group's project turns out to be "the agent has the tools but keeps doing it wrong",
you have found a skill, not a server. That is a legitimate hackathon outcome and a faster one.
The whole format is:

```
my-skill/
└── SKILL.md        # ---\nname: my-skill\ndescription: ...\n---\n then Markdown
```
