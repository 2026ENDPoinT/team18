"""Independently verify saved CERs with a standard-library DP implementation."""
import argparse
import hashlib
import json
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent

def norm(text, no_space):
    text = unicodedata.normalize("NFC", text)
    return "".join(c for c in text if not c.isspace()) if no_space else text

def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        nxt = [i]
        for j, y in enumerate(b, 1):
            nxt.append(min(row[j] + 1, nxt[-1] + 1, row[j - 1] + (x != y)))
        row = nxt
    return row[-1]

def verify(results):
    summary = json.loads((results / "summary.json").read_text())
    manifest = json.loads((BASE / "manifest.json").read_text())
    assert len(summary["samples"]) == len(manifest["samples"])
    assert norm("한\t글\nA1!", True) == "한글A1!"
    assert distance("가나다", "가라다") == 1
    assert distance("가나다", "가다") == 1
    assert distance("가나다", "가나다!") == 1
    assert distance("가나다", "") == 3
    sums = {key: [0, 0] for key in ["with_whitespace", "without_whitespace"]}
    for row in summary["samples"]:
        for key in ["image", "ground_truth"]:
            assert hashlib.sha256((BASE / row[key]).read_bytes()).hexdigest() == row[key + "_sha256"]
        gt = (BASE / row["ground_truth"]).read_text()
        prediction = (results / row["prediction"]).read_text()
        for key, no_space in [("with_whitespace", False), ("without_whitespace", True)]:
            a, b = norm(gt, no_space), norm(prediction, no_space)
            d = distance(a, b)
            metric = row[key]
            assert d == metric["errors"] == sum(metric[x] for x in ["insertions", "deletions", "substitutions"])
            assert metric["reference_characters"] == len(a)
            assert metric["cer"] == d / len(a)
            if row["status"] in ["empty", "error"]:
                assert metric["deletions"] == len(a) and d == len(a)
            sums[key][0] += d; sums[key][1] += len(a)
    for key, (errors, chars) in sums.items():
        metric = summary["groups"]["all_inputs"][key]
        assert metric["cer"] == errors / chars
        assert metric["errors"] == errors and metric["reference_characters"] == chars
    result = {"verified_samples": len(summary["samples"]), "verified_metrics": 2 * len(summary["samples"]),
              "method": "independent standard-library Levenshtein DP, input hashes, normalization and micro aggregation checks", "all_passed": True}
    (results / "verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--results", type=Path, default=BASE / "results")
    verify(parser.parse_args().results)
