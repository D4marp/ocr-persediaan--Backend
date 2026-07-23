"""
Hitung akurasi OCR (Tesseract) terhadap ground truth nota UMKM yang
ditranskrip manual dari foto nota asli (bukan sintetis).

Dua metrik dilaporkan (umum dipakai pada evaluasi OCR dokumen/nota,
mis. gaya SROIE/CORD):
  1. Field Detection Rate - apakah tiap field kunci (no nota, toko,
     nama barang, nominal) berhasil "ditemukan" di teks hasil OCR
     (token-overlap + fuzzy match per token).
  2. Field-level Character Accuracy (1 - CER) - untuk field yang
     ditemukan, seberapa mirip (karakter demi karakter, Levenshtein)
     teks OCR di lokasi field tsb terhadap nilai ground truth. Dihitung
     per-field (bukan CER global atas seluruh dokumen) karena ground
     truth cuma berisi field terstruktur, bukan transkrip penuh nota
     (header/alamat toko dsb tidak tercatat di spreadsheet sumber).
"""
import json
import os
import re
import difflib

BASE = os.path.dirname(__file__)
GT_PATH = os.path.join(BASE, "data", "nota_ground_truth.json")
MATCH_PATH = "/private/tmp/claude-502/-Users-HCMPublic-Downloads-ocr-persediaan/acf33744-4ec8-4241-b341-6379d93b2ebc/scratchpad/image_matches_all.json"
OCR_PATH = os.path.join(BASE, "data", "ocr_results.json")
OUT_PATH = os.path.join(BASE, "data", "accuracy_report.json")


def norm_text(s):
    if s is None:
        return ""
    s = str(s).upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_digits(s):
    return re.sub(r"[^0-9]", "", str(s) or "")


def levenshtein(a, b):
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def field_char_accuracy(value_norm, ocr_norm):
    """
    CER lokal per-field: cari posisi kemunculan field yang paling mirip di
    dalam teks OCR (bukan global diff atas seluruh dokumen, karena field
    ground truth cuma sebagian kecil dari teks nota penuh - global CER akan
    salah besar karena header/alamat toko dsb tidak ada di ground truth).
    """
    if not value_norm:
        return None
    if value_norm in ocr_norm:
        return 1.0
    if not ocr_norm:
        return 0.0
    sm = difflib.SequenceMatcher(None, ocr_norm, value_norm, autojunk=False)
    match = sm.find_longest_match(0, len(ocr_norm), 0, len(value_norm))
    center = match.a + match.size // 2 if match.size else len(ocr_norm) // 2
    n = len(value_norm)
    best_dist = n
    for w in (n, n + 4, max(1, n - 4), n + 8):
        start = max(0, center - w // 2)
        end = min(len(ocr_norm), start + w)
        d = levenshtein(value_norm, ocr_norm[start:end])
        best_dist = min(best_dist, d)
    return max(0.0, 1 - best_dist / max(1, n))


def token_found(field_value, ocr_norm_tokens, ocr_norm_text):
    """Cek apakah suatu field (string) 'ditemukan' di teks OCR."""
    fv = norm_text(field_value)
    if not fv or fv == "-":
        return None  # field kosong/tidak berlaku, skip dari skor
    if fv in ocr_norm_text:
        return 1.0
    tokens = [t for t in fv.split(" ") if len(t) >= 3]
    if not tokens:
        return 1.0 if fv in ocr_norm_text else 0.0
    hit = 0
    for t in tokens:
        best = max((difflib.SequenceMatcher(None, t, ot).ratio() for ot in ocr_norm_tokens), default=0)
        if best >= 0.8 or t in ocr_norm_text:
            hit += 1
    return hit / len(tokens)


def number_found(value_thousands, ocr_digit_text):
    """value_thousands: nilai dalam satuan ribuan (spt di ground truth)."""
    try:
        v = float(value_thousands)
    except (TypeError, ValueError):
        return None
    rupiah = int(round(v * 1000))
    digits = str(rupiah)
    if len(digits) < 3:
        return None
    if digits in ocr_digit_text:
        return 1.0
    # toleransi: mungkin OCR salah 1 digit -> cek substring tanpa 1 digit terakhir/awal
    if len(digits) >= 4 and (digits[:-1] in ocr_digit_text or digits[1:] in ocr_digit_text):
        return 0.5
    return 0.0


def main():
    gt = json.load(open(GT_PATH))
    matches = json.load(open(MATCH_PATH))
    ocr = json.load(open(OCR_PATH))

    # Matcher agents wrote free-text no_nota/toko (sometimes with notes,
    # garbled OCR readings, parentheticals). Do fuzzy best-match against
    # the (small) candidate list per book instead of requiring exact
    # string equality.
    def find_records(kind, no_nota, toko):
        no_nota_n = norm_text(no_nota)
        toko_n = norm_text(toko)
        best, best_score = None, 0.0
        for r in gt[kind]["records"]:
            r_no = norm_text(r["no_nota"])
            r_toko = norm_text(r["toko_supplier"])
            s_no = difflib.SequenceMatcher(None, no_nota_n, r_no).ratio()
            # also reward if the GT id's alnum core appears as substring either way
            if r_no and (r_no in no_nota_n or no_nota_n[:len(r_no)] == r_no):
                s_no = max(s_no, 0.9)
            s_toko = difflib.SequenceMatcher(None, toko_n, r_toko).ratio()
            score = 0.7 * s_no + 0.3 * s_toko
            if score > best_score:
                best_score, best = score, r
        return [best] if best is not None and best_score >= 0.35 else []

    per_image = []
    for link_id, m in matches.items():
        matched_in = m.get("matched_in") or []
        if not matched_in:
            continue
        link_key = link_id  # e.g. link05_<driveid>
        short_id = link_key.split("_", 1)[0]  # link05
        if short_id not in ocr:
            continue
        ocr_entry = ocr[short_id]
        ocr_text = ocr_entry.get("text", "")
        ocr_norm = norm_text(ocr_text)
        ocr_tokens = [t for t in ocr_norm.split(" ") if t]
        ocr_digits = norm_digits(ocr_text)

        records = []
        for kind in matched_in:
            records.extend(find_records(kind, m.get("no_nota", ""), m.get("toko", "")))
        if not records:
            continue

        field_scores = []   # deteksi field (0/1-ish, token overlap)
        char_scores = []    # akurasi karakter lokal per-field (CER-based)
        detail = {"no_nota": None, "toko": None, "tanggal": None, "items": []}

        toko_val = records[0]["toko_supplier"]
        s = token_found(toko_val, ocr_tokens, ocr_norm)
        if s is not None:
            field_scores.append(s)
            char_scores.append(field_char_accuracy(norm_text(toko_val), ocr_norm))
            detail["toko"] = s

        no_nota_val = records[0]["no_nota"]
        s = token_found(no_nota_val, ocr_tokens, ocr_norm)
        if s is not None:
            field_scores.append(s)
            char_scores.append(field_char_accuracy(norm_text(no_nota_val), ocr_norm))
            detail["no_nota"] = s

        for rec in records:
            for item in rec["items"]:
                s_name = token_found(item["nama_barang"], ocr_tokens, ocr_norm)
                if s_name is not None:
                    field_scores.append(s_name)
                    char_scores.append(field_char_accuracy(norm_text(item["nama_barang"]), ocr_norm))
                s_amt = number_found(item.get("total_harga"), ocr_digits)
                if s_amt is not None:
                    field_scores.append(s_amt)
                detail["items"].append({
                    "nama_barang": item["nama_barang"],
                    "name_score": s_name,
                    "total_harga_score": s_amt,
                })

        field_acc = sum(field_scores) / len(field_scores) if field_scores else None
        cacc = sum(char_scores) / len(char_scores) if char_scores else None

        per_image.append({
            "link": link_key,
            "matched_in": matched_in,
            "no_nota": no_nota_val,
            "toko": toko_val,
            "n_items": sum(len(r["items"]) for r in records),
            "ocr_mode": ocr_entry.get("ocr_mode"),
            "ocr_confidence": ocr_entry.get("confidence"),
            "field_accuracy": field_acc,
            "char_accuracy": cacc,
            "detail": detail,
        })

    valid_field = [p["field_accuracy"] for p in per_image if p["field_accuracy"] is not None]
    valid_char = [p["char_accuracy"] for p in per_image if p["char_accuracy"] is not None]

    summary = {
        "n_images_evaluated": len(per_image),
        "n_images_total_downloaded": len(matches),
        "n_images_unmatched": sum(1 for m in matches.values() if not m.get("matched_in")),
        "mean_field_detection_rate_pct": round(100 * sum(valid_field) / len(valid_field), 2) if valid_field else None,
        "mean_field_char_accuracy_pct": round(100 * sum(valid_char) / len(valid_char), 2) if valid_char else None,
    }

    out = {"summary": summary, "per_image": per_image}
    json.dump(out, open(OUT_PATH, "w"), ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2))
    print("Saved detail to", OUT_PATH)


if __name__ == "__main__":
    main()
