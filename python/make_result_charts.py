"""
Buat figure grafik (bukan teks) untuk paper: bar chart hasil utama dengan
error bar CI 95% bootstrap, dan chart ablation radius dilasi.

Semua angka nyata dari evaluasi (score_fa_ocr / bootstrap).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DOCS = "/Users/HCMPublic/Downloads/ocr-persediaan/docs"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.linewidth": 0.7,
    "axes.edgecolor": "#333333",
})

# ---- data nyata (field detection %, dgn 95% CI bootstrap) ----
cats = ["Thermal", "Handwritten", "Dot-matrix", "Aggregate"]
base = [87.9, 25.8, 21.0, 46.7]
base_lo = [76.3, 15.0, 9.2, 34.3]
base_hi = [96.3, 36.7, 35.4, 59.2]
fa = [87.0, 33.3, 87.3, 80.4]
fa_lo = [76.1, 22.5, 81.9, 72.9]
fa_hi = [95.0, 42.5, 92.1, 87.3]
# EasyOCR hanya pada dot-matrix
easy_dm, easy_lo, easy_hi = 54.5, 40.6, 67.9


def err(vals, lo, hi):
    return [np.array(vals) - np.array(lo), np.array(hi) - np.array(vals)]


# =========== FIGURE A: hasil utama ===========
fig, ax = plt.subplots(figsize=(6.6, 2.9))
x = np.arange(len(cats))
w = 0.38

b1 = ax.bar(x - w/2, base, w, yerr=err(base, base_lo, base_hi),
            capsize=3, color="#ffffff", edgecolor="#222222", linewidth=0.9,
            hatch="////", label="Baseline (Tesseract)", error_kw={"elinewidth": 0.8})
b2 = ax.bar(x + w/2, fa, w, yerr=err(fa, fa_lo, fa_hi),
            capsize=3, color="#4a4a4a", edgecolor="#222222", linewidth=0.9,
            label="FA-OCR", error_kw={"elinewidth": 0.8, "ecolor": "#000000"})

# titik EasyOCR pada dot-matrix (indeks 2)
ax.errorbar(2, easy_dm, yerr=[[easy_dm - easy_lo], [easy_hi - easy_dm]],
            fmt="D", color="#c0392b", markersize=6, capsize=3, elinewidth=0.9,
            markeredgecolor="#000000", markeredgewidth=0.5, label="EasyOCR (dot-matrix)", zorder=5)

# label nilai di atas whisker CI atas (hindari tumpang tindih)
for xi, v, hi in zip(x - w/2, base, base_hi):
    ax.text(xi, hi + 1.5, f"{v:.1f}", ha="center", va="bottom", fontsize=7.5)
for xi, v, hi in zip(x + w/2, fa, fa_hi):
    ax.text(xi, hi + 1.5, f"{v:.1f}", ha="center", va="bottom", fontsize=7.5, fontweight="bold")
ax.text(2.30, easy_dm, f"{easy_dm:.1f}", ha="left", va="center", fontsize=7.5, color="#c0392b")

ax.set_ylabel("Field detection rate (%)")
ax.set_xticks(x)
ax.set_xticklabels(cats)
ax.set_ylim(0, 108)
ax.set_yticks([0, 20, 40, 60, 80, 100])
ax.legend(loc="upper center", ncol=3, frameon=False, fontsize=7.6,
          bbox_to_anchor=(0.5, 1.16), columnspacing=1.2, handletextpad=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", linewidth=0.4, color="#dddddd")
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{DOCS}/fig4_results.pdf", bbox_inches="tight")
fig.savefig(f"{DOCS}/fig4_results.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("saved fig4_results")

# =========== FIGURE B: ablation radius (inverted-U) ===========
fig, ax = plt.subplots(figsize=(3.3, 2.5))
radii = [1, 2, 3]
dm_dil = [72.6, 87.3, 71.5]
th_dil = [86.2, 87.0, 80.6]
ax.plot(radii, dm_dil, "o-", color="#222222", linewidth=1.4, markersize=6,
        label="Dot-matrix", markeredgecolor="#000000")
ax.plot(radii, th_dil, "s--", color="#888888", linewidth=1.2, markersize=5,
        label="Thermal")
# titik closing r=2 (lebih buruk dari dilasi)
ax.plot([2], [71.9], "x", color="#c0392b", markersize=9, markeredgewidth=1.8,
        label="Closing (r=2)", zorder=5)
for r, v in zip(radii, dm_dil):
    ax.text(r, v + 1.6, f"{v:.1f}", ha="center", fontsize=7.5, fontweight="bold")
ax.text(2.08, 71.9, "71.9", ha="left", va="center", fontsize=7.2, color="#c0392b")
ax.set_xlabel("Dilation radius $r$")
ax.set_ylabel("Dot-matrix field detection (%)")
ax.set_xticks([1, 2, 3])
ax.set_ylim(66, 92)
ax.legend(loc="lower center", frameon=False, fontsize=7.2, handletextpad=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", linewidth=0.4, color="#dddddd")
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{DOCS}/fig5_ablation.pdf", bbox_inches="tight")
fig.savefig(f"{DOCS}/fig5_ablation.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("saved fig5_ablation")
