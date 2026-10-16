# Autonomous Step 0 agent evaluation

Use the [Agents SDK benchmark guide](../chromatin-trace-mcp/benchmarks/agent_step0/README.md)
for environment setup, live/offline commands, disclosure controls and measurement definitions.
The [implementation report](../STEP0_AGENT_BENCHMARK_REPORT.md) records the checks run.

This is an optional evaluation client, not scientific processing or a new pipeline step.
A exposes six separate Step 0 tools; B exposes only the aggregate validator.
Both create Markdown/HTML reports automatically within the trace validation call.
No report-server tool, connection or model round trip is required. Each
live trial is a fresh SDK conversation with dynamic tool selection and no oracle
answers. Tool allowlisting is enforced at discovery and dispatch; experiment roots
and policy are immutable for a trial. Do not use the older fixed-route prompt
controls as evidence of autonomous agent behavior.

Only provider-reported usage counts as actual tokens. Null usage and NOT RUN live
status must remain explicit. Offline SDK doubles test plumbing, not autonomy.
Review free-text answers against the independent oracle: typed factual scores do
not establish complete narrative accuracy. Never interpret a Step 0 PASS as a
biological conclusion. Do not implement or invoke Step 1 through this harness.
