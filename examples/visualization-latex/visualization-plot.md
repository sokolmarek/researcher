# Example: Publication-Quality Line Plot

| Field | Value |
|---|---|
| Skill | visualization |
| Command | n/a |
| Trigger phrase | "Plot the label-efficiency results: macro-AUROC vs labeled fraction for each method" |
| Connectors used | none |
| Generated | 2026-07-12; rendered with matplotlib on this date |

## Invocation

> Plot my label-efficiency results: macro-AUROC on the y-axis, labeled fraction (1%, 10%, 100%) on a log x-axis, one line per method, colorblind-safe, publication style. Mark it as synthetic demonstration data.

## Input

The same `(synthetic, for demonstration)` results as the `latex-results-table` example, so the table and the chart tell one story.

```csv
method,frac_1,frac_10,frac_100
CNN (from scratch),0.712,0.848,0.921
CNN + augmentation,0.741,0.863,0.924
Contrastive (baseline),0.803,0.881,0.926
+ physio. augment (ours),0.821,0.889,0.929
```

## Output

Rendered with `matplotlib` (Agg backend), saved at 150 DPI.

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fracs = [1, 10, 100]
series = {
    "CNN (from scratch)":       ([0.712, 0.848, 0.921], "#8c8c8c", "o", "--"),
    "CNN + augmentation":       ([0.741, 0.863, 0.924], "#5b5b5b", "s", "--"),
    "Contrastive (baseline)":   ([0.803, 0.881, 0.926], "#0072B2", "^", "-"),
    "+ physio. augment (ours)": ([0.821, 0.889, 0.929], "#D55E00", "D", "-"),
}
plt.rcParams.update({"font.size": 12, "axes.linewidth": 0.8})
fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
for name, (vals, color, marker, ls) in series.items():
    ax.plot(fracs, vals, marker=marker, linestyle=ls, color=color,
            linewidth=2.2, markersize=7, label=name)
ax.set_xscale("log")
ax.set_xticks(fracs)
ax.set_xticklabels(["1%", "10%", "100%"])
ax.set_xlabel("Labeled fraction of PTB-XL (log scale)")
ax.set_ylabel("Macro-AUROC (superclass)")
ax.set_ylim(0.68, 0.94)
ax.grid(True, which="both", alpha=0.25, linewidth=0.6)
ax.legend(loc="lower right", frameon=True, framealpha=0.95, fontsize=10.5)
ax.set_title("Label efficiency: self-supervised pretraining vs supervised")
fig.text(0.99, 0.01, "Synthetic data, for demonstration only", ha="right",
         va="bottom", fontsize=8.5, color="#888888", style="italic")
fig.tight_layout()
fig.savefig("label-efficiency-plot.png", bbox_inches="tight", facecolor="white")
```

![Label-efficiency line plot: self-supervised curves sit above the supervised baselines, with the gap largest at the 1% labeled fraction](../../assets/img/examples/label-efficiency-plot.png)

## What this demonstrates

- The visualization skill picks a chart type (a line plot on a log x-axis) that fits the question (a trend across labeled fractions), rather than defaulting to bars.
- The palette is colorblind-safe (the same blue and orange used in the architecture diagram), and self-supervised methods are solid lines while supervised baselines are dashed, so the two families read apart at a glance.
- The chart reuses the exact numbers from the `latex-results-table` example, so the table and the figure are consistent, and the synthetic-data caveat rides along in the corner.
- The story the plot makes visible: the self-supervised advantage is largest in the low-label regime (1%) and narrows toward parity at 100%, which is the label-efficiency claim the manuscript makes.
