# Step 0 measurement and benchmark protocol

## Two separate boundaries

The MCP server records execution time, structured parameter/response JSON bytes,
files/records/findings and outcome for each new Step 0 tool. It does not know which
model is used by its client or how many context, cached, output or reasoning
tokens that model consumes. Response bytes are not tokens.

The optional agent harness records the actual Responses API `usage` object for
every model response, including responses that select tools and the final answer.
It retains response/model identifiers and deduplicates response IDs. Run totals
are sums over responses. Cached tokens are a subset of input tokens; reasoning
tokens are a subset of output tokens. They are not added again to total tokens.
Missing fields remain null, and any missing response makes the corresponding
run total unavailable rather than a misleading partial total.

Provider schema and tool-call protocol were checked against official OpenAI
[reasoning documentation](https://developers.openai.com/api/docs/guides/reasoning)
and [function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling)
on 16 October 2026. The API harness is opt-in, uses no new SDK dependency, and is
not a replacement for a client-specific adapter when another provider is used.
The desktop MCP connection does not expose this chat's provider usage. An
external client's genuine usage export can be passed to `UsageRecorder.record`;
response-size estimates cannot be substituted for it.

No live provider usage was collected during implementation because credentials
were not available. Usage parser tests use explicitly synthetic records; those
values are not reported as measurements. The API agent path is implemented but
has not been tested against a live model. Setup requires a model selected by the
operator and provider credentials in the client environment, never in a prompt,
repository file or report. No API key is requested by the MCP server itself.

## Controlled task strategies

Six natural-language prompts in `benchmarks/benchmark_step0.py` cover discovered
ROI counts, required files, missing barcodes, affected ROIs, a report and readiness.
`benchmarks/create_fixture.py` creates a two-ROI example and an independently
specified oracle. Trace and localization coverage are not combined; missing-barcode
answer checks refer explicitly to trace coverage.

- A: five separate MCP calls: inspection, discovery, structure, ECSV validation,
  then saved-report retrieval. The full validator has already produced the report.
- B: one `run_experiment_validation` call with detailed output.
- C: compact aggregate validation; cached ROI details only when the question needs
  missing barcode identifiers. No table reanalysis for follow-up details.
- D: direct deterministic Python execution without an LLM or MCP transport.

Default A/B/C execution is a **scripted MCP control**, not an agent. Its answers
are extracted from saved evidence to measure validator/transport correctness and
latency. D has zero LLM tokens by construction. A/B/C provider-token values are
null in this mode; zero is not substituted.

With `--agent`, an actual model selects among the strategy's allowed tools and
returns a constrained JSON fact answer to each natural-language prompt. The harness
records model-selected calls/arguments, final response, per-response usage and
latency. It checks facts against the independent oracle, detects unsupported fact
fields, and rejects changed experiment roots or validation criteria. A sequence
violation is a failed strategy run. Agent execution is bounded to 12 response
rounds and 20 tool calls. Raw scientific records and images are never sent.

The oracle verifies explicit structured claims, not arbitrary scientific prose.
A separate evaluator would be needed for unconstrained narrative conclusions.
This benchmark does not prove the reliability of future scientific analysis.

## Reproduction

From the trace package with its test dependencies installed:

```bash
python benchmarks/create_fixture.py /tmp/step0-benchmark
export CHROMATIN_EXPERIMENT_ROOTS=/tmp/step0-benchmark/experiment
export CHROMATIN_STEP0_OUTPUT_DIR=/tmp/step0-benchmark-output
python benchmarks/benchmark_step0.py \
  --root /tmp/step0-benchmark/experiment \
  --rules /tmp/step0-benchmark/rules.json \
  --oracle /tmp/step0-benchmark/oracle.json \
  --output /tmp/step0-benchmark-results.json --repeats 3
```

For a real agent benchmark, configure `OPENAI_API_KEY` securely in the shell and
repeat the same command with `--agent --model <explicit-model-id>`. This makes
provider API requests and sends the compact scientific summaries; it is not
performed by default. Use the same exact model and prompt settings for all agent
strategies. Preserve returned resolved model identifiers, rules, independent
oracle and source commit alongside results. The harness does not set temperature
because model support varies; report this default as a limitation.

Optional `--pricing <json>` accepts operator-provided dated pricing with keys
`input_per_million`, `cached_per_million`, `output_per_million`. No current price is
guessed. Cost is unknown without both prices and required token fields. Pricing
metadata should record currency/date/model/source. Reasoning is included in output
billing, and cached input replaces the corresponding uncached-input charge.

Results include accuracy, explicit missing-barcode false positives/negatives,
failure rate, per-prompt repeatability, tool calls, tool and end-to-end latency,
usage and cost when available. Tokens per success use all attempted-run tokens
in the numerator, including failures. Token reductions use agent strategy A,
not the zero-token deterministic baseline. Calls per successful task are likewise
calculated over attempts. No percentage is computed when a denominator or provider
usage is unavailable.

The committed `benchmarks/results_summary.json` contains sanitized transport-control
results only. Full local traces and report artifacts are produced by a fresh run;
raw experimental data and machine-specific dataset locations are not committed.

## Future image-versus-numeric experiment

After native analyzer outputs have machine-readable contracts, compare figure
paths only, numeric summaries plus figure paths, and opt-in multimodal figure
interpretation. Fix datasets, model, prompts, parameter settings and numerical
oracle; repeat runs. Record actual usage, latency, cost, exact numeric errors,
failure rates and interpretability. Do not obtain scientific numbers from pixels
when the original arrays are available. No multimodal benchmark is implemented
or claimed in Step 0.
