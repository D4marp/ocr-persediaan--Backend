"""
Dua figure tambahan untuk memperkuat paper (data nyata, bukan rekaan):
1. Confusion matrix classifier (LOO-CV, format_pred_loo.json vs format_labels.json)
2. Scatter confidence vs field accuracy per format (fa_ocr_scored_r2_dilate.json)
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = "/Users/HCMPublic/Downloads/ocr-persediaan/backend/python"
DOCS = "/Users/HCMPublic/Downloads/ocr-persediaan/docs"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.linewidth": 0.7,
    "axes.edgecolor": "#333333",
})

# ---------- FIGURE: confusion matrix ----------
pred = json.load(open(f"{BASE}/data/format_pred_loo.json"))
labels = json.load(open(f"{BASE}/data/format_labels.json"))
true = {k: v["format"] for k, v in labels.items()}

cats = ["thermal_clean", "handwritten", "dot_matrix"]
disp = ["Thermal", "Handwritten", "Dot-matrix"]
idx = {c: i for i, c in enumerate(cats)}
M = np.zeros((3, 3), dtype=int)
for k, p in pred.items():
    t = true.get(k)
    if t is None:
        continue
    M[idx[t], idx[p]] += 1

fig, ax = plt.subplots(figsize=(3.3, 3.0))
im = ax.imshow(M, cmap="Greys", vmin=0, vmax=M.max())
for i in range(3):
    for j in range(3):
        v = M[i, j]
        color = "white" if v > M.max() * 0.55 else "black"
        ax.text(j, i, str(v), ha="center", va="center", fontsize=11,
                fontweight="bold" if i == j else "normal", color=color)
ax.set_xticks(range(3))
ax.set_yticks(range(3))
ax.set_xticklabels(disp, fontsize=8)
ax.set_yticklabels(disp, fontsize=8, rotation=90, va="center")
ax.set_xlabel("Predicted (leave-one-out)")
ax.set_ylabel("True format")
ax.set_xticks(np.arange(-0.5, 3, 1), minor=True)
ax.set_yticks(np.arange(-0.5, 3, 1), minor=True)
ax.grid(which="minor", color="#888888", linewidth=0.6)
ax.tick_params(which="minor", length=0)
n = M.sum()
acc = np.trace(M) / n
ax.set_title(f"LOO-CV accuracy: {acc*100:.1f}% ({int(np.trace(M))}/{n})", fontsize=8.5)
fig.tight_layout()
fig.savefig(f"{DOCS}/fig6_confusion.pdf", bbox_inches="tight")
fig.savefig(f"{DOCS}/fig6_confusion.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("saved fig6_confusion, M=\n", M, "acc=", acc)

# ---------- FIGURE: confidence vs field accuracy scatter ----------
scored = json.load(open(f"{BASE}/data/fa_ocr_scored_r2_dilate.json"))
fmt_style = {
    "thermal_clean": dict(marker="o", color="#222222", label="Thermal"),
    "handwritten":   dict(marker="^", color="#888888", label="Handwritten"),
    "dot_matrix":    dict(marker="s", color="#c0392b", label="Dot-matrix"),
}
fig, ax = plt.subplots(figsize=(3.4, 2.7))
for fmt, style in fmt_style.items():
    xs = [x["confidence"] for x in scored if x["format_true"] == fmt and x["confidence"] is not None and x["field_accuracy"] is not None]
    ys = [x["field_accuracy"] * 100 for x in scored if x["format_true"] == fmt and x["confidence"] is not None and x["field_accuracy"] is not None]
    if not xs:
        continue
    ax.scatter(xs, ys, marker=style["marker"], color=style["color"], s=26,
               edgecolor="#000000", linewidth=0.4, label=style["label"], alpha=0.85, zorder=3)
    if len(xs) >= 2:
        b, a = np.polyfit(xs, ys, 1)
        xr = np.linspace(min(xs), max(xs), 20)
        ax.plot(xr, a + b * xr, "-", color=style["color"], linewidth=1.1, alpha=0.7, zorder=2)

ax.set_xlabel("OCR confidence")
ax.set_ylabel("Field accuracy (%)")
ax.set_ylim(-5, 108)
ax.legend(loc="lower left", frameon=True, facecolor="white", edgecolor="none",
          framealpha=0.92, fontsize=7.2, handletextpad=0.4, borderpad=0.4)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", linewidth=0.4, color="#dddddd")
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{DOCS}/fig7_confidence_scatter.pdf", bbox_inches="tight")
fig.savefig(f"{DOCS}/fig7_confidence_scatter.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("saved fig7_confidence_scatter")
