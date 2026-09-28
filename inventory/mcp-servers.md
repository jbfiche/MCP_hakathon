# MCP servers for cancer systems biology

Statuses are defined in [`README.md`](README.md): **confirmed** is vouched for or official,
**candidate** is unvetted. Verified September 2026.

---

## Mechanistic modelling — the closest thing to our own field

### `mcp-biomodelling-servers` — NeKo, MaBoSS, PhysiCell/PhysiBoSS

**Status: confirmed.** Start here. This is the reference example for everything the hackathon is
about, and it is built on the same SDK v2 the demo plugins in this repo use.

- Repository: <https://github.com/marcorusc/mcp-biomodelling-servers>
- PyPI: `mcp-biomodelling-servers` · MCP Registry: `io.github.marcorusc/{NeKo,MaBoSS,PhysiCell}`
- Author: Marco Ruscone (with Miguel Vazquez and Alfonso Valencia)
- Paper: *Intelligent tool orchestration for rapid mechanistic model prototyping: MCP servers as
  AI-biology interfaces*, **npj Systems Biology and Applications** (2026),
  [10.1038/s41540-026-00767-3](https://doi.org/10.1038/s41540-026-00767-3)

Three **stateful** stdio servers, distributed as one package:

| Server | Role | Upstream |
| --- | --- | --- |
| `mcp-neko-server` | build and analyse signalling networks from interaction databases | [NeKo](https://github.com/sysbio-curie/Neko) |
| `mcp-maboss-server` | configure, simulate and analyse stochastic Boolean models | [pyMaBoSS](https://github.com/colomoto/pyMaBoSS) |
| `mcp-physicell-server` | build, inspect and export PhysiCell/PhysiBoSS configurations | [PhysiCell_Settings](https://github.com/marcorusc/PhysiCell_Settings) |

```bash
uvx --from mcp-biomodelling-servers mcp-neko-server
```

Requires Python 3.10–3.14, and the Graphviz `dot` binary for NeKo history diagrams (`dot -V` to
check — the Python `graphviz` package is not a substitute).

**Why read the source.** It is a working answer to the questions every group will hit on Day 2:
how to hold modelling state across tool calls (`session_manager.py`), how to separate the tool
surface from the science (`tools/` vs `services/`), how to hand off between servers
(`services/handoff.py`), and how to write guidance into the server so the agent orchestrates the
three in the right order (`guidance.py`). Also see the companion
[`Supp_mat_MCP_orchestrator`](https://github.com/marcorusc/Supp_mat_MCP_orchestrator), which
records what different LLMs produced from the same prompt.

---

## Broad biomedical aggregators

### BioMCP

**Status: confirmed.** <https://biomcp.org> · <https://github.com/genomoncology/biomcp> · MIT ·
`mcp-name: io.github.genomoncology/biomcp`

One binary over a single command grammar reaching ~30 biomedical sources — PubMed/PubTator3,
Europe PMC, ClinVar, ClinicalTrials.gov, OncoKB, Reactome and others — usable both as a CLI and
as an MCP server. Notable for cancer work: gene/variant/drug/disease/pathway pivoting,
g:Profiler enrichment, and local cohort analytics (query, survival, compare, co-occurrence) over
downloaded cBioPortal-style datasets.

```bash
uv tool install biomcp-cli     # NOT `pip install biomcp`, which is an unrelated package
biomcp health --apis-only
biomcp search all --gene BRAF --disease melanoma
docker run --rm -i ghcr.io/genomoncology/biomcp serve    # as an MCP server
```

Worth studying for how it handles identifier deduplication across sources (PMID/PMCID/DOI) — the
unglamorous work that makes a multi-source server actually usable.

---

## Anthropic's Claude for Life Sciences marketplace

**Status: confirmed** as a distribution channel. <https://github.com/anthropics/life-sciences>

A Claude Code plugin marketplace holding 21 plugins: 15 MCP connectors and 6 skills. Most
connectors are remote HTTP servers, so there is nothing to install and nothing to maintain —
which also means you cannot read their source. Install the marketplace with:

```
/plugin marketplace add anthropics/life-sciences
```

| Plugin | Provider | Endpoint owner |
| --- | --- | --- |
| `pubmed` | U.S. National Library of Medicine | official |
| `open-targets` | Open Targets | official |
| `10x-genomics` | 10x Genomics Cloud | official |
| `synapse` | Sage Bionetworks | official |
| `biorender` | BioRender | official |
| `medidata` | Medidata | official |
| `consensus` | Consensus | official |
| `cortellis` | Clarivate | official |
| `adisinsight` | Springer Nature | official |
| `wiley-scholar-gateway` | Wiley | official |
| `owkin` | Owkin | official |
| `tooluniverse` | ToolUniverse | third-party |
| `chembl`, `clinical-trials`, `biorxiv` | deepsense.ai | third-party wrapper of a public API |

Skills in the same marketplace: `single-cell-rna-qc` (scverse best practices),
`scvi-tools`, `nextflow-development` (nf-core rnaseq/sarek/atacseq on local or GEO/SRA data),
`instrument-data-to-allotrope`, `clinical-trial-protocol`, `scientific-problem-selection`.

Several of these are directly relevant to a cancer group: Open Targets for target–disease
association, PubMed for literature, Synapse for shared cohort data, `nextflow-development` and
`single-cell-rna-qc` for actual analysis.

---

## Augmented Nature — one server per public database

**Status: candidate.** <https://github.com/Augmented-Nature> · <https://augmentednature.ai>

23 MCP servers, one per public biological database, unaffiliated with the databases themselves.
Broad coverage, quick to try, uneven documentation; several are explicitly labelled
"unofficial". Useful as a **starting point to read and fork** rather than as infrastructure —
and useful as a reality check on which databases are already covered.

| Server | ★ | Server | ★ |
| --- | --- | --- | --- |
| ChEMBL | 89 | KEGG | 11 |
| PubChem | 47 | Open Targets *(unofficial)* | 11 |
| AlphaFold | 35 | BioOntology | 9 |
| PDB | 25 | Gene Ontology | 8 |
| UniProt | 20 | ClinicalTrials | 8 |
| OpenFDA | 21 | SureChEMBL | 7 |
| NCBI Datasets | 16 | BioThings | 6 |
| PubMed | 15 | ProteinAtlas | 4 |
| Reactome | 12 | STRING-db | 4 |
| | | Ensembl, GTEx, HPO | 3 each |
| | | BioStudies | 2 |
| | | OpenGenes | 1 |

Where a server exists both here and in Anthropic's marketplace (ChEMBL, Open Targets, PubMed,
ClinicalTrials), prefer the marketplace one: the provider or a funded partner maintains it.

---

## Gaps worth building

Checked against GitHub, the MCP registries and mcp.so/glama.ai in September 2026. Three status
terms recur below: **confirmed gap** (no server of any kind found), **still open** (a server
exists but does not close the gap, because it reads cached files instead of the live API, or has
no real users), and **not a gap** (usable coverage exists).

- **cBioPortal** as a live client is still open. The official
  [`cbioportal-mcp`](https://github.com/cBioPortal/cbioportal-mcp) queries a ClickHouse mirror,
  not the live REST API; an unofficial server that does hit the live API exists
  ([pickleton89/cbioportal-mcp](https://github.com/pickleton89/cbioportal-mcp), 6★) but has no
  adoption to speak of. BioMCP separately analyses *downloaded* cBioPortal-style data.
- **COSMIC**, **CellMinerCDB**: confirmed gaps.
- **MSigDB / GSEA**: confirmed gap, save for
  [montilab/SigRepo_Server](https://github.com/montilab/SigRepo_Server) (0★), which treats
  MSigDB as one of several signature backends rather than a dedicated target.
- **DepMap**: still open. An unofficial server exists
  ([saurabhsing21/deepmap-mcp](https://github.com/saurabhsing21/deepmap-mcp), 1★), but like the
  cBioPortal case above it reads a locally-downloaded CRISPR-screen CSV cache, not the live API.
- **OmniPath / pypath** directly: NeKo reaches it, but there is no general OmniPath server.
- **CellNOptTools**, **CoLoMoTo notebook**, **GINsim**, **BoolNet**: the Boolean-modelling
  ecosystem beyond MaBoSS. Confirmed gaps, all four.
- Anything institutional: a lab's own cohort, LIMS, image store or pipeline outputs.

That last category is the one where a hackathon group has an unfair advantage: you have the data
and the domain knowledge, and nobody outside your institute can build it for you.
