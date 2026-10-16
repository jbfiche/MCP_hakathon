# Autonomous Step 0 agent benchmark

This harness uses OpenAI Agents SDK 0.24.0 and a real subprocess MCP connection.
The live path uses `Agent` + `Runner.run` + dynamically discovered MCP tools.
There is no prompt-to-tool routing table. Each prompt/repeat/configuration gets a
new Agent, model client, stdio process, output directory and conversation. No session,
conversation ID, prior response ID, fixture label or expected answer is supplied.
The independent oracle remains outside model context.

## Setup

Keep this benchmark environment separate from the scientific server environment.
Python 3.13 was used for the recorded checks. From the repository root:

```sh
python3.13 -m venv /tmp/step0-agent-env
/tmp/step0-agent-env/bin/pip install -r chromatin-trace-mcp/benchmarks/agent_step0/requirements.lock.txt
```

Copy `config.example.json` to a **private location outside Git** and replace every
placeholder with an absolute path. Use your already validated MCP interpreter,
working directory, entrypoint and PYTHONPATH. `real_experiment` is the original
reference experiment: the harness reads it for independent counting and hashes,
then copies only the selected four mask-based trace/localization tables. The server
is authorized only for each trial's copy, never the original source. Raw matrices,
images and `full_pwd` / `PWD_comparison` contents are not loaded or copied.

Run all offline checks first, with a new output directory outside experimental data:

```sh
/tmp/step0-agent-env/bin/python chromatin-trace-mcp/benchmarks/agent_step0/benchmark_agent.py \
  --config /private/path/step0-agent.local.json --output /private/path/benchmark-offline
STEP0_AGENT_TEST_CONFIG=/private/path/step0-agent.local.json \
  /tmp/step0-agent-env/bin/python -m pytest chromatin-trace-mcp/benchmarks/agent_step0/test_agent_benchmark.py -q
```

Without `STEP0_AGENT_TEST_CONFIG`, two stdio/SDK tests are explicitly skipped.
The scripted Model in those two tests is a protocol double, **not** autonomous
model evidence. Offline controls use fixed tool calls by design and are labeled
`offline_scripted_mcp`, separate from `live_agent` records.

For live runs, configure an API key in the calling terminal without putting it in
the config file, shell history, repository or conversation. In zsh:

```sh
read -rs 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
export STEP0_BENCHMARK_MODEL='your-accessible-model-id'
/tmp/step0-agent-env/bin/python chromatin-trace-mcp/benchmarks/agent_step0/benchmark_agent.py \
  --config /private/path/step0-agent.local.json --output /private/path/benchmark-live \
  --live --model "$STEP0_BENCHMARK_MODEL" --trials 3
unset OPENAI_API_KEY
```

No model is silently selected. An API account with access to the selected model is
needed; signing into the desktop app does not configure this script's API key.
Defaults schedule 120 independent trials: four synthetic cases × five prompts ×
two configurations × three repeats. Add `--include-real` only after reviewing data
disclosure; this adds 30 trials on the selected real-data copy. The same settings
and deterministic shuffled order apply to both configurations. Use a fresh output
directory for every invocation. No credentials means no live benchmark; offline
results must not be described as autonomous success.

## Safeguards and scope

- A exposes six Step 0 tools; B exposes only `run_experiment_validation`.
  Discovery filters and dispatch checks both enforce the allowlist. Every other
  tool, including existing processing tools, is denied. This does not change the
  server's global tool catalog for other clients.
- Trial roots and scientific policy are fixed. Arguments are schema checked;
  alternate roots, changed rules and foreign cached run IDs are rejected. The
  caller still chooses available tools, paging, output level and follow-up calls.
- Maximum eight tool attempts, ten agent turns, 1,600 output tokens per model
  response, 180 seconds per trial, 30 seconds per MCP request, 48,000 canonical
  result bytes per call and 160,000 total result bytes per trial. Responses over
  budget are withheld. SDK/provider retries are disabled. Trials are capped at ten
  repeats. Limits bound execution; they are not an exact monetary spending limit.
- Copies are read-only (files 0444; directories 0555); originals and copies are
  fingerprinted before/after. Reports stay outside inputs. Permissions and
  application allowlists are **not an OS sandbox**: the server runs as the current
  user, who could change permissions. For hostile code, add a container with a
  read-only fixture mount, no original-data mount and network/resource limits.
- Initial live tests use synthetic, blinded fixture paths. Real paths, metadata,
  tool schemas/results and prompts can reach the provider with `--include-real`.
  API secrets are removed from the MCP child environment. SDK tracing is disabled
  and model response storage is disabled (`store=False`). This does not promise
  zero provider retention; review your account's data policy before real-data use.
- Logs are private by default (umask 077). They contain answers, calls, paths and
  bounded metadata, so keep them outside Git. Delete/archive them under your lab's
  retention policy. This harness does not upload traces or report files elsewhere.

## Evaluation and measurements

`reference.py` independently counts rows, ROI IDs and barcodes using stdlib CSV,
without importing the validator. It supports the reviewed space-delimited ECSV
1.0 subset, not arbitrary ECSV. Synthetic expectations are explicit fixture design:
two ROIs and two barcodes. Real expected acquisition ROI/barcode sets remain unknown,
so the real copy should remain `INCOMPLETE`; observed IDs do not establish design.
Missing barcode observations are warnings under the default policy, yielding PASS
with that warning; they do not demonstrate biological failure.

Final answers have an ordinary text answer plus typed factual claims. Exact
deterministic scoring checks requested fields, any additional asserted typed facts,
tool evidence, report artifacts and absence of typed scientific conclusions. Wrong
or missing facts fail. Free text is retained for **independent human review**;
automatic typed scores do not certify every prose claim or scientific conclusion.
Do not advertise narrative accuracy without that review.

`records.json` records direct deterministic subprocesses, individual scripted MCP
controls and, when run, live agent trials. Direct duration includes process startup;
individual tool durations exclude MCP startup. Agent total duration includes startup,
discovery and orchestration; provider duration is separately recorded. These scopes
are deliberately distinct. A control uses `validate_ecsv_tables`; B uses the full
aggregate. These controls are not an A-versus-B agent-efficiency conclusion.

Actual provider `usage` is captured before SDK normalization, with returned model ID,
input/output/total/cached/reasoning tokens when present. Missing values remain null.
No token count is estimated from bytes. Failed requests are retained, with null usage
if no provider usage was returned. Cost remains null because no pricing is assumed;
apply verified pricing for the returned model if needed. SDK integration and usage
parsing tests use synthetic usage and must never be included in actual-token totals.

Outputs include `records.json`, `accuracy_summary.json`, `trial_plan.json`, environment
versions/limits, source/copy integrity, independent oracle results, per-run reports,
and `COMPARISON_REPORT.md`. A skipped live run is recorded explicitly. Partial runs
retain results in the finalizer, but interrupted processes/power loss may need review.

Official background: [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk).
This harness was checked against installed SDK source; dependencies are frozen for
the benchmark environment. No Traceratops scientific functions are changed, and
Step 1 remains outside this milestone.

## Single-call Data Quality Reports

Both full trace validation tools save Markdown and HTML alongside JSON evidence.
The benchmark agent uses returned paths; it needs no report-server connection.
`get_validation_summary` retrieves cached paths without revalidating. A exposes
six separate trace tools; B exposes only the aggregate. Existing report-server
comparison/PDF tools are outside this Step 0 benchmark.
