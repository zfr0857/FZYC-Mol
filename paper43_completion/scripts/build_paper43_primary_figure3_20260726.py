from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image, ImageDraw


ROOT = Path(r"D:\fzyc")
OUT = ROOT / "output" / "paper43_jcheminform_completion_20260726"
TABLES = OUT / "additional_files" / "tables"
FIGURES = OUT / "figures"
SOURCE = OUT / "qc_main_image5.png"


def forest_axis(ax, frame, labels, color, xlabel):
    frame = frame.set_index("dataset").loc[list(labels)].reset_index()
    y = list(range(len(frame)))
    estimates = frame["mean_natural_scale_effect"]
    low = frame["seed_block_interval_low"]
    high = frame["seed_block_interval_high"]
    for row, (estimate, lo, hi) in enumerate(zip(estimates, low, high, strict=True)):
        excludes = lo > 0 or hi < 0
        ax.errorbar(
            estimate,
            row,
            xerr=[[estimate - lo], [hi - estimate]],
            fmt="o",
            ms=7,
            color=color,
            markerfacecolor=color if excludes else "white",
            markeredgewidth=1.5,
            capsize=3,
            linewidth=1.5,
        )
    ax.axvline(0, color="#333333", linewidth=1.0)
    ax.set_yticks(y, list(labels.values()), fontsize=12)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=12)
    ax.grid(axis="x", alpha=0.18)
    ax.tick_params(axis="x", labelsize=11)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)


def main():
    original = Image.open(SOURCE).convert("RGB")
    width, height = original.size
    split_x, split_y = 2050, 1700
    panel_width, panel_height = split_x, height - split_y

    effects = pd.read_csv(TABLES / "fixed_reference_k32_vs_k4_contrasts.csv")
    effects = effects[effects.estimand == "fixed_k32_gap"].copy()
    classification = effects[effects.task_type == "classification"]
    regression = effects[effects.task_type == "regression"]

    plt.rcParams.update({"font.family": "Arial"})
    fig = plt.figure(figsize=(panel_width / 200, panel_height / 200), dpi=200)
    grid = fig.add_gridspec(1, 2, left=0.12, right=0.98, top=0.80, bottom=0.18, wspace=0.55)
    ax_c = fig.add_subplot(grid[0, 0])
    ax_r = fig.add_subplot(grid[0, 1])
    forest_axis(
        ax_c,
        classification,
        {"tdc_hia_hou": "HIA", "clintox": "ClinTox", "bace": "BACE", "bbbp": "BBBP", "tdc_pgp_broccatelli": "P-gp"},
        "#326596",
        "K=32 − K=4 completion-gap contrast\n(ROC-AUC)",
    )
    forest_axis(
        ax_r,
        regression,
        {"esol": "ESOL", "lipo": "Lipophilicity", "tdc_caco2_wang": "Caco2", "freesolv": "FreeSolv"},
        "#D8782A",
        "K=32 − K=4 completion-gap contrast\n(RMSE)",
    )
    fig.text(0.015, 0.96, "C", fontsize=25, fontweight="bold", va="top")
    fig.text(0.09, 0.96, "K-invariant full-registry effects", fontsize=19, fontweight="bold", va="top")
    fig.text(0.09, 0.865, "Ten split seeds; negative values indicate a smaller completion gap at K=32", fontsize=11.5, va="top")
    fig.text(0.50, 0.055, "Filled markers: split-seed sensitivity interval excludes zero; open markers: interval includes zero", ha="center", fontsize=10)
    temp = FIGURES / "Figure_3_panel_C_primary.png"
    fig.savefig(temp, dpi=200, facecolor="white")
    plt.close(fig)

    panel_c = Image.open(temp).convert("RGB")
    if panel_c.size != (panel_width, panel_height):
        panel_c = panel_c.resize((panel_width, panel_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(original.crop((0, 0, split_x, split_y)), (0, 0))
    canvas.paste(original.crop((split_x, 0, width, split_y)), (split_x, 0))
    canvas.paste(panel_c, (0, split_y))
    canvas.paste(original.crop((split_x, split_y, width, height)), (split_x, split_y))
    # Remove the clipped remnant of the old panel-C tick label at the panel seam.
    ImageDraw.Draw(canvas).rectangle((2010, 1960, 2115, 2085), fill="white")
    png = FIGURES / "Figure_3_primary_estimand_aligned.png"
    pdf = FIGURES / "Figure_3_primary_estimand_aligned.pdf"
    canvas.save(png, dpi=(300, 300))
    canvas.save(pdf, "PDF", resolution=300)
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
