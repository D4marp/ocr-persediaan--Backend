"""
Figur demonstrasi proses FA-OCR: nota input -> output pipeline (nyata).
Semua angka dari fa_ocr.run() pada nota asli link30 (Depo Lestari, Banjarmasin).
"""
import sys
sys.path.insert(0, ".")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import fa_ocr

IMG = "data/raw_notas/link30_1nazJNcHpgYRNF77AJ4mrnew7zzwCK6rG.jpg"
DOCS = "/Users/HCMPublic/Downloads/ocr-persediaan/docs/riset/img"

res = fa_ocr.run(IMG)
fmt = res["format"]
conf = res["confidence"]
psm = res["per_psm_conf"]
feat = res["features"]
decision = res["decision"]
text = res["text"]

fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 7.5),
                               gridspec_kw={"width_ratios": [1, 1.25]})

# --- kiri: nota asli ---
img = mpimg.imread(IMG)
axL.imshow(img, cmap="gray")
axL.axis("off")
axL.set_title("(a) Citra nota input\n(struk thermal, UMKM Banjarmasin)", fontsize=11)

# --- kanan: output pipeline ---
axR.axis("off")
fmt_label = {"thermal_clean": "Thermal", "dot_matrix": "Dot-matrix", "handwritten": "Tulisan tangan"}.get(fmt, fmt)
lines = []
lines.append(("Tahap I — Klasifikasi Format", "head"))
lines.append((f"Format terdeteksi : {fmt_label}", "b"))
lines.append((f"Fitur run-length  : cv_run={feat['cv_run']:.2f}, short_run={feat['short_run_ratio']:.2f}", "n"))
lines.append((f"Fitur morfologi   : ink_gain={feat['ink_gain']:.2f}, run_gain={feat['run_gain']:.2f}", "n"))
lines.append(("", "sp"))
lines.append(("Tahap III — Fusi Multi-PSM (Tesseract)", "head"))
lines.append((f"PSM 3: {psm.get(3,0):.1f}   PSM 4: {psm.get(4,0):.1f}   "
              f"PSM 6: {psm.get(6,0):.1f}   PSM 11: {psm.get(11,0):.1f}", "n"))
lines.append((f"Confidence gabungan : {conf:.1f}", "b"))
lines.append(("", "sp"))
lines.append(("Tahap IV — Keputusan Routing", "head"))
dec_txt = "Verifikasi manusia" if decision == "verify" else "Terima otomatis"
lines.append((f"Keputusan : {dec_txt}", "b"))
lines.append(("", "sp"))
lines.append(("Teks hasil ekstraksi (petikan):", "head"))
snippet = text[:230].replace("\n", " ")
# bungkus manual
import textwrap
for wl in textwrap.wrap(snippet, width=52)[:6]:
    lines.append(("  " + wl, "mono"))

y = 0.97
for txt_line, kind in lines:
    if kind == "head":
        axR.text(0.0, y, txt_line, fontsize=10.5, fontweight="bold", color="#1a1a1a",
                 transform=axR.transAxes, va="top")
        y -= 0.052
    elif kind == "b":
        axR.text(0.02, y, txt_line, fontsize=10, color="#0b5", fontweight="bold",
                 transform=axR.transAxes, va="top", family="DejaVu Sans")
        y -= 0.048
    elif kind == "mono":
        axR.text(0.02, y, txt_line, fontsize=8.5, color="#333", family="DejaVu Sans Mono",
                 transform=axR.transAxes, va="top")
        y -= 0.038
    elif kind == "sp":
        y -= 0.022
    else:
        axR.text(0.02, y, txt_line, fontsize=9.5, color="#333",
                 transform=axR.transAxes, va="top", family="DejaVu Sans")
        y -= 0.046

axR.set_title("(b) Keluaran pipeline FA-OCR", fontsize=11)
# kotak border kanan
axR.add_patch(plt.Rectangle((-0.02, 0.0), 1.02, 1.0, fill=False, lw=0.8,
              edgecolor="#bbb", transform=axR.transAxes, clip_on=False))

fig.tight_layout()
fig.savefig(f"{DOCS}/fig_ocr_process.png", dpi=200, bbox_inches="tight")
print("saved fig_ocr_process.png")
print(f"format={fmt} conf={conf:.1f} decision={decision}")
