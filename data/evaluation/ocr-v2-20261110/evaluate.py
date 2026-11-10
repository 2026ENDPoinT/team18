"""Offline, unmodified service OCR; NFC micro CER with raw predictions and times."""
import argparse
import collections
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
COMMIT = "46e777ed1a1e180188c0f2ff17384fd58932a780"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()

def hardware():
    # Metadata collection must not fail OCR when macOS sandbox denies sysctl.
    if sys.platform == "darwin":
        try:
            info = json.loads(subprocess.check_output(["system_profiler", "SPHardwareDataType", "-json"], text=True))["SPHardwareDataType"][0]
            return {k: info[k] for k in ["chip_type", "physical_memory", "machine_model", "number_processors"] if k in info}
        except Exception as error:
            return {"processor": platform.processor(), "probe_error": str(error)}
    return {"processor": platform.processor()}

def score(reference, prediction, remove_whitespace=False):
    from rapidfuzz.distance import Levenshtein
    a, b = [unicodedata.normalize("NFC", x) for x in (reference, prediction)]
    if remove_whitespace:
        a, b = ["".join(c for c in x if not c.isspace()) for x in (a, b)]
    counts = collections.Counter(op.tag for op in Levenshtein.editops(a, b))
    errors = sum(counts.values())
    assert errors == Levenshtein.distance(a, b)
    assert len(b) == len(a) + counts["insert"] - counts["delete"]
    return {"reference_characters": len(a), "prediction_characters": len(b),
            "insertions": counts["insert"], "deletions": counts["delete"],
            "substitutions": counts["replace"], "errors": errors, "cer": errors / len(a),
            "exact_match": a == b}

def aggregate(rows):
    result = {"inputs": len(rows), "original_documents": len({r["original_id"] for r in rows}),
              "success": sum(r["status"] == "success" for r in rows),
              "empty": sum(r["status"] == "empty" for r in rows),
              "errors": sum(r["status"] == "error" for r in rows)}
    times = [r["seconds"] for r in rows if r["status"] != "error"]
    result["median_seconds"] = statistics.median(times) if times else None
    result["min_seconds"] = min(times) if times else None
    result["max_seconds"] = max(times) if times else None
    for metric in ["with_whitespace", "without_whitespace"]:
        sums = {key: sum(r[metric][key] for r in rows) for key in
                ["reference_characters", "prediction_characters", "insertions", "deletions", "substitutions", "errors"]}
        sums["cer"] = sums["errors"] / sums["reference_characters"] if sums["reference_characters"] else None
        result[metric] = sums
    return result

def run(out):
    if out.exists():
        raise RuntimeError(f"Refusing to overwrite results: {out}")
    assert git("rev-parse", "HEAD") == COMMIT, "Source commit differs from the audited commit."
    manifest = json.loads((BASE / "manifest.json").read_text())
    assert sha(BASE / "protocol.md") == manifest["protocol_sha256"]
    for sample in manifest["samples"]:
        for key in ["image", "ground_truth"]:
            assert sha(BASE / sample[key]) == sample[key + "_sha256"], (sample["id"], key)
    out.mkdir(parents=True)
    (out / "predictions").mkdir()
    (out / "sample_scores").mkdir()
    tracked_before = git("diff", "--binary", "HEAD")
    code_paths = [REPO / "ai/local/ocr.py", REPO / "ai/intake.py", REPO / "ai/workflow.py", REPO / "ai/gemini/roadmap.mjs"]
    model_paths = sorted((REPO / "ai/models/ocr-v2").glob("*")) + sorted((REPO / "ai/models/ocr-detector").glob("*"))
    hashes = {str(p.relative_to(REPO)): sha(p) for p in code_paths + model_paths if p.is_file()}
    start = time.perf_counter()
    import torch
    sys.path.insert(0, str(REPO / "ai"))
    from local.ocr import LocalOCR
    import_seconds = time.perf_counter() - start
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    metadata = {"commit": COMMIT, "branch": git("branch", "--show-current"),
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "os": platform.platform(), "machine": platform.machine(),
        "hardware": hardware(),
        "cpu_count": os.cpu_count(), "torch_threads": torch.get_num_threads(),
        "torch_interop_threads": torch.get_num_interop_threads(), "cuda_available": torch.cuda.is_available(),
        "mps_available": torch.backends.mps.is_available(), "import_seconds": import_seconds,
        "package_versions": {p: importlib.metadata.version(p) for p in
             ["torch", "torchvision", "transformers", "pillow", "numpy", "opencv-python-headless", "pypdfium2", "rapidfuzz"]},
        "source_hashes": hashes, "manifest_sha256": sha(BASE / "manifest.json"),
        "settings": {"model": "local", "orientation": "auto", "layout": "rows", "crop_padding": 0},
        "error_scoring": "error predictions replaced by empty string for conservative full-input CER; successful-return-only also reported",
        "timing": "PNG bytes already in memory -> LocalOCR.extract -> returned text; 1 trial per input, separate non-scored warmup"}
    start = time.perf_counter()
    try:
        engine = LocalOCR("local")
    except Exception:
        metadata["load_error"] = traceback.format_exc()
        metadata["model_load_seconds"] = time.perf_counter() - start
        save(out / "environment.json", metadata)
        raise
    metadata["model_load_seconds"] = time.perf_counter() - start
    metadata["device"] = engine.device
    metadata["detector_class"] = type(engine.dm).__name__
    metadata["recognizer_class"] = type(engine.rm).__name__
    metadata["recognizer_parameters"] = sum(p.numel() for p in engine.rm.parameters())
    metadata["detector_parameters"] = sum(p.numel() for p in engine.dm.parameters())
    warmup = (BASE / "qa/warmup.png").read_bytes()
    start = time.perf_counter()
    metadata["warmup_output"] = engine.extract("png", warmup)
    metadata["warmup_seconds"] = time.perf_counter() - start
    save(out / "environment.json", metadata)
    print(json.dumps({"event": "loaded", "device": engine.device, "model_load_seconds": metadata["model_load_seconds"], "warmup_seconds": metadata["warmup_seconds"]}), flush=True)
    rows = []
    # Fixed manifest order, all samples are scored even on empty output/error.
    for sample in manifest["samples"]:
        raw = (BASE / sample["image"]).read_bytes()
        reference = (BASE / sample["ground_truth"]).read_text(encoding="utf-8")
        error = None
        if engine.device == "cuda": torch.cuda.synchronize()
        start = time.perf_counter()
        try:
            pages = engine.extract("png", raw)
            if engine.device == "cuda": torch.cuda.synchronize()
            seconds = time.perf_counter() - start
            assert len(pages) == 1
            prediction = pages[0][1]
            status = "success" if prediction.strip() else "empty"
        except Exception:
            seconds = time.perf_counter() - start
            error = traceback.format_exc()
            prediction, status = "", "error"
        pred_path = out / "predictions" / (sample["id"] + ".txt")
        pred_path.write_text(prediction, encoding="utf-8")
        row = {**sample, "prediction": str(pred_path.relative_to(out)), "status": status,
               "seconds": seconds, "error": error, "with_whitespace": score(reference, prediction),
               "without_whitespace": score(reference, prediction, True)}
        rows.append(row)
        save(out / "sample_scores" / (sample["id"] + ".json"), row)
        print(json.dumps({"event": "sample", "id": row["id"], "status": status, "seconds": seconds,
                          "cer": row["with_whitespace"]["cer"], "cer_no_space": row["without_whitespace"]["cer"]}), flush=True)
    groups = {"all_inputs": rows, "originals_only": [r for r in rows if r["variant"] == "base"],
              "successful_returns_only": [r for r in rows if r["status"] != "error"]}
    for kind in ["real", "synthetic"]:
        groups[kind] = [r for r in rows if r["kind"] == kind]
        for variant in ["base", "half", "blur"]:
            subset = [r for r in rows if r["kind"] == kind and r["variant"] == variant]
            if subset: groups[kind + "_" + variant] = subset
    summary = {"groups": {name: aggregate(items) for name, items in groups.items()}, "samples": rows}
    save(out / "summary.json", summary)
    fields = ["id", "kind", "variant", "status", "seconds", "reference_characters", "insertions", "deletions", "substitutions", "cer", "cer_without_whitespace"]
    with (out / "scores.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row[k] for k in fields[:5]},
                             **{k: row["with_whitespace"][k] for k in fields[5:-1]},
                             "cer_without_whitespace": row["without_whitespace"]["cer"]})
    assert tracked_before == git("diff", "--binary", "HEAD"), "Tracked working changes changed."
    assert hashes == {str(p.relative_to(REPO)): sha(p) for p in code_paths + model_paths if p.is_file()}
    metadata["source_unchanged_after_run"] = True
    metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    save(out / "environment.json", metadata)
    print(json.dumps({"event": "complete", **summary["groups"]["all_inputs"]}), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=BASE / "results")
    run(parser.parse_args().output.resolve())
