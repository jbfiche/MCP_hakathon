"""Create a small synthetic benchmark with an independently specified oracle."""
import json
from pathlib import Path
from astropy.table import Table


def create_fixture(destination: Path):
    root = destination / "experiment"
    root.mkdir(parents=True, exist_ok=True)
    for rid, barcodes in [(92, [1, 3]), (93, [2, 3])]:
        folder = root / f"{rid:03d}"
        trace = folder / "tracing/data" / f"Trace_3D_barcode_mask-mask0_ROI-{rid}.ecsv"
        loc = folder / "localize_3d/data/localizations_3D_barcode.ecsv"
        trace.parent.mkdir(parents=True, exist_ok=True)
        loc.parent.mkdir(parents=True, exist_ok=True)
        Table({"Spot_ID": [f"s{rid}-{b}" for b in barcodes], "Trace_ID": [f"n{rid}"] * 2,
               "ROI #": [rid] * 2, "Barcode #": barcodes,
               "x": [0., 1.], "y": [0., 0.], "z": [0., 0.]}).write(trace, format="ascii.ecsv", overwrite=True)
        Table({"Buid": [f"s{rid}-{b}" for b in barcodes], "ROI #": [rid] * 2, "Barcode #": barcodes,
               "xcentroid": [0., 1.], "ycentroid": [0., 0.], "zcentroid": [0., 0.]}).write(loc, format="ascii.ecsv", overwrite=True)
    rules = {"expected_roi_ids": ["92", "93"], "expected_barcodes": ["1", "2", "3"], "barcode_source": "synthetic experiment design"}
    oracle = {"roi_count": 2, "complete_file_rois": 2, "error_count": 0, "warning_count": 4, "status": "PASS", "missing_barcodes_by_roi": {"92": ["2"], "93": ["1"]}, "readiness": "review_warnings"}
    (destination / "rules.json").write_text(json.dumps(rules, indent=2))
    (destination / "oracle.json").write_text(json.dumps(oracle, indent=2))
    return root


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(create_fixture(parser.parse_args().destination))
