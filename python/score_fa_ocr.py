"""
Menilai hasil FA-OCR dengan metrik yang IDENTIK dengan baseline
(compute_accuracy.py), sehingga perbandingannya sah.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from compute_accuracy import (field_char_accuracy, norm_digits, norm_text,
                              number_found, token_found)
import difflib

BASE = os.path.dirname(__file__)
GT = json.load(open(os.path.join(BASE, "data", "nota_ground_truth.json")))
MATCHES = json.load(open(os.path.join(BASE, "data", "image_matches_all.json")))
LABELS = {k: v["format"] for k, v in json.load(open(os.path.join(BASE, "data", "format_labels.json"))).items()}


def find_records(kind, no_nota, toko):
    no_nota_n, toko_n = norm_text(no_nota), norm_text(toko)
    best, best_score = None, 0.0
    for r in GT[kind]["records"]:
        r_no, r_toko = norm_text(r["no_nota"]), norm_text(r["toko_supplier"])
        s_no = difflib.SequenceMatcher(None, no_nota_n, r_no).ratio()
        if r_no and (r_no in no_nota_n or no_nota_n[:len(r_no)] == r_no):
            s_no = max(s_no, 0.9)
        s_toko = difflib.SequenceMatcher(None, toko_n, r_toko).ratio()
        score = 0.7 * s_no + 0.3 * s_toko
        if score > best_score:
            best_score, best = score, r
    return [best] if best is not None and best_score >= 0.35 else []


def score(ocr_map):
    per_image = []
    for link_id, m in MATCHES.items():
        matched_in = m.get("matched_in") or []
        if not matched_in:
            continue
        lid = link_id.split("_", 1)[0]
        if lid not in ocr_map:
            continue
        entry = ocr_map[lid]
        text = entry.get("text", "")
        ocr_norm = norm_text(text)
        tokens = [t for t in ocr_norm.split(" ") if t]
        digits = norm_digits(text)

        records = []
        for kind in matched_in:
            records.extend(find_records(kind, m.get("no_nota", ""), m.get("toko", "")))
        if not records:
            continue

        fs, cs = [], []
        toko_val = records[0]["toko_supplier"]
        s = token_found(toko_val, tokens, ocr_norm)
        if s is not None:
            fs.append(s)
            cs.append(field_char_accuracy(norm_text(toko_val), ocr_norm))
        no_val = records[0]["no_nota"]
        s = token_found(no_val, tokens, ocr_norm)
        if s is not None:
            fs.append(s)
            cs.append(field_char_accuracy(norm_text(no_val), ocr_norm))
        for rec in records:
            for item in rec["items"]:
                sn = token_found(item["nama_barang"], tokens, ocr_norm)
                if sn is not None:
                    fs.append(sn)
                    cs.append(field_char_accuracy(norm_text(item["nama_barang"]), ocr_norm))
                sa = number_found(item.get("total_harga"), digits)
                if sa is not None:
                    fs.append(sa)
        per_image.append({
            "link": lid,
            "format_true": LABELS.get(lid),
            "format_pred": entry.get("format_pred"),
            "confidence": entry.get("confidence"),
            "field_accuracy": sum(fs) / len(fs) if fs else None,
            "char_accuracy": sum(cs) / len(cs) if cs else None,
        })
    return per_image


def summarize(per_image, tag):
    fa = [p["field_accuracy"] for p in per_image if p["field_accuracy"] is not None]
    ca = [p["char_accuracy"] for p in per_image if p["char_accuracy"] is not None]
    print(f"\n=== {tag} (n={len(per_image)}) ===")
    print(f"  overall field={100*sum(fa)/len(fa):.1f}%  char={100*sum(ca)/len(ca):.1f}%")
    for fmt in ("thermal_clean", "handwritten", "dot_matrix"):
        rows = [p for p in per_image if p["format_true"] == fmt]
        if not rows:
            continue
        f = [r["field_accuracy"] for r in rows if r["field_accuracy"] is not None]
        c = [r["char_accuracy"] for r in rows if r["char_accuracy"] is not None]
        print(f"  {fmt:15s} n={len(rows):2d} field={100*sum(f)/len(f):5.1f}%  char={100*sum(c)/len(c):5.1f}%")
    return {"field": 100 * sum(fa) / len(fa), "char": 100 * sum(ca) / len(ca), "n": len(per_image)}


def main():
    summary = {}
    for path in sorted(glob.glob(os.path.join(BASE, "data", "fa_ocr_results_*.json"))):
        tag = os.path.basename(path).replace("fa_ocr_results_", "").replace(".json", "")
        ocr_map = json.load(open(path))
        pi = score(ocr_map)
        summary[tag] = summarize(pi, f"FA-OCR {tag}")
        json.dump(pi, open(os.path.join(BASE, "data", f"fa_ocr_scored_{tag}.json"), "w"), indent=2)

    baseline = json.load(open(os.path.join(BASE, "data", "ocr_results.json")))
    pi = score(baseline)
    summary["baseline"] = summarize(pi, "BASELINE (single-best PSM, no routing)")
    json.dump(summary, open(os.path.join(BASE, "data", "fa_ocr_summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
