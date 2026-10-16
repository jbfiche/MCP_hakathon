"""Instrumentation tests use synthetic usage payloads, never claim live usage."""
import importlib.util
from pathlib import Path

path = Path(__file__).parents[1] / "benchmarks/benchmark_step0.py"
spec = importlib.util.spec_from_file_location("step0_benchmark", path)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_provider_usage_adds_responses_without_double_counting_cached_or_reasoning():
    recorder = benchmark.UsageRecorder()
    response = {"id": "synthetic-response-1", "model": "synthetic-test-model", "usage": {
        "input_tokens": 100, "output_tokens": 30, "total_tokens": 130,
        "input_tokens_details": {"cached_tokens": 70}, "output_tokens_details": {"reasoning_tokens": 20}}}
    recorder.record(response)
    recorder.record(response)  # Duplicate provider response is not another charge.
    recorder.record({**response, "id": "synthetic-response-2"})
    assert recorder.totals() == {"input_tokens": 200, "output_tokens": 60, "total_tokens": 260, "cached_tokens": 140, "reasoning_tokens": 40}


def test_missing_usage_and_optional_fields_are_unknown_not_zero():
    recorder = benchmark.UsageRecorder()
    assert all(v is None for v in recorder.totals().values())
    recorder.record({"id": "synthetic-1", "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}})
    assert recorder.totals()["total_tokens"] == 8
    assert recorder.totals()["cached_tokens"] is None
    recorder.record({"id": "synthetic-2", "usage": None})
    assert recorder.totals()["total_tokens"] is None


def test_oracle_counts_wrong_barcode_claims_and_unsupported_fields():
    oracle = {"missing_barcodes_by_roi": {"92": ["2"], "93": ["1"]}}
    answer = {"missing_barcodes_by_roi": {"92": ["99"], "93": []}, "biologically_equivalent": True}
    result = benchmark.score(answer, oracle, ["missing_barcodes_by_roi"])
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 2
    assert not result["successful"]
    assert result["unsupported_claim_fields"] == ["biologically_equivalent"]


def test_cost_requires_explicit_price_and_usage():
    usage = {"input_tokens": 100, "cached_tokens": 60, "output_tokens": 20}
    assert benchmark.cost(usage, None) is None
    assert benchmark.cost(usage, {"input_per_million": 2, "cached_per_million": 1, "output_per_million": 4}) == 220 / 1_000_000
