"""Render fixed sources and freeze image/GT hashes before any OCR inference."""
import argparse
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from fontTools.ttLib import TTFont
import pypdfium2 as pdfium

BASE = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def prepare(freeze=False):
    if (BASE / "results").exists():
        raise RuntimeError("Results already exist: do not regenerate scored input/GT.")
    for dirname in ["images", "ground_truth", "qa"]:
        (BASE / dirname).mkdir(exist_ok=True)
    manifest, qa = [], []
    for source in json.loads((BASE / "sources/synthetic_sources.json").read_text()):
        sid = source["id"]
        gt_lines = [source["title"], *source["lines"]]
        if "rows" in source:
            gt_lines += ["\t".join(source["columns"])]
            gt_lines += ["\t".join(row) for row in source["rows"]]
        gt_lines += source.get("footer", [])
        gt = unicodedata.normalize("NFC", "\n".join(gt_lines))
        # Save the reference before rendering, never derived from an OCR prediction.
        gt_path = BASE / "ground_truth" / (sid + ".txt")
        gt_path.write_text(gt, encoding="utf-8")
        font_path = BASE / "sources/fonts" / source["font"]
        cmap = TTFont(font_path).getBestCmap()
        missing = sorted({c for c in gt if not c.isspace() and ord(c) not in cmap})
        if missing:
            raise ValueError(f"Missing glyphs: {sid}: {missing}")
        im = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(im)
        title_font = ImageFont.truetype(str(font_path), 40)
        body_font = ImageFont.truetype(str(font_path), 28)
        boxes = []

        def text(x, y, value, font=body_font):
            bbox = draw.textbbox((x, y), value, font=font)
            if not (20 <= bbox[0] < bbox[2] <= 1220 and 20 <= bbox[1] < bbox[3] <= 1734):
                raise ValueError(f"Clipped text: {sid}: {value}: {bbox}")
            draw.text((x, y), value, font=font, fill=(15, 20, 30))
            boxes.append({"text": value, "bbox": bbox})

        text(70, 80, source["title"], title_font)
        draw.line((70, 148, 1170, 148), fill=(80, 100, 125), width=2)
        y = 185
        for line in source["lines"]:
            text(70, y, line)
            y += 65
        if "rows" in source:
            y += 20
            xs = [70, 545, 665, 820, 1170]
            for row_index, row in enumerate([source["columns"], *source["rows"]]):
                if row_index == 0:
                    draw.rectangle((70, y, 1170, y + 70), fill=(232, 238, 245))
                for j, cell in enumerate(row):
                    text(xs[j] + 14, y + 17, cell)
                    if boxes[-1]["bbox"][2] >= xs[j + 1] - 8:
                        raise ValueError(f"Cell overflow: {sid}: {cell}")
                draw.line((70, y, 1170, y), fill=(100, 110, 120), width=1)
                y += 70
            draw.line((70, y, 1170, y), fill=(100, 110, 120), width=1)
            table_top = y - 70 * (len(source["rows"]) + 1)
            for x in xs:
                draw.line((x, table_top, x, y), fill=(100, 110, 120), width=1)
            y += 40
        for line in source.get("footer", []):
            text(70, y, line)
            y += 65
        qa.append({"id": sid, "font": source["font"], "font_sha256": digest(font_path),
                   "missing_glyphs": missing, "all_text_within_canvas_and_cells": True, "text_boxes": boxes})
        variants = {"base": im, "half": im.resize((620, 877), Image.Resampling.LANCZOS),
                    "blur": im.filter(ImageFilter.GaussianBlur(1.2))}
        for variant, image in variants.items():
            sample_id = sid + "_" + variant
            path = BASE / "images" / (sample_id + ".png")
            image.save(path)
            manifest.append({"id": sample_id, "original_id": sid, "kind": "synthetic",
                             "category": source["category"], "variant": variant,
                             "image": str(path.relative_to(BASE)), "ground_truth": str(gt_path.relative_to(BASE)),
                             "width": image.width, "height": image.height})
    for source in json.loads((BASE / "sources/real_sources.json").read_text()):
        sid = source["id"]
        with pdfium.PdfDocument(str(BASE / "sources" / source["file"])) as pdf:
            assert len(pdf) == 1
            image = pdf[0].render(scale=2).to_pil()
            path = BASE / "images" / (sid + ".png")
            image.save(path)
        manifest.append({"id": sid, "original_id": sid, "kind": "real", "variant": "base",
                         "category": source["name"], "image": str(path.relative_to(BASE)),
                         "ground_truth": "ground_truth/" + sid + ".txt",
                         "width": image.width, "height": image.height, "pdf_scale": 2,
                         "source_pdf_sha256": source["sha256"]})
    # Non-scored full-path warmup image.
    warmup = Image.new("RGB", (600, 180), "white")
    d = ImageDraw.Draw(warmup)
    f = ImageFont.truetype(str(BASE / "sources/fonts/NanumGothic-Regular.ttf"), 28)
    d.text((30, 40), "모델 실행 준비 123", font=f, fill="black")
    warmup.save(BASE / "qa/warmup.png")
    write_json(BASE / "qa/render_checks.json", qa)
    if freeze:
        visual = json.loads((BASE / "qa/visual_review.json").read_text())
        assert visual["review_completed_before_ocr"] is True
        for sample in manifest:
            for key in ["image", "ground_truth"]:
                sample[key + "_sha256"] = digest(BASE / sample[key])
        write_json(BASE / "manifest.json", {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                   "protocol_sha256": digest(BASE / "protocol.md"), "samples": manifest})
    else:
        write_json(BASE / "qa/draft_manifest.json", manifest)
    print(f"Prepared {len(manifest)} inputs, {len(set(s['original_id'] for s in manifest))} originals; frozen={freeze}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--freeze", action="store_true")
    prepare(p.parse_args().freeze)
