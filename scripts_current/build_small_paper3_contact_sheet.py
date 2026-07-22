from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "output" / "小论文-3_图表包" / "figures"
OUT = ROOT / "output" / "小论文-3_图表包" / "contact_sheet.png"


def main() -> None:
    paths = sorted(FIG_DIR.glob("fig*.png"))
    fig, axes = plt.subplots(5, 2, figsize=(15, 21), facecolor="white")
    for ax, path in zip(axes.ravel(), paths):
        ax.imshow(plt.imread(path))
        ax.set_title(path.stem, fontsize=12, loc="left", pad=5)
        ax.axis("off")
    for ax in axes.ravel()[len(paths):]:
        ax.axis("off")
    fig.subplots_adjust(left=0.015, right=0.985, top=0.985, bottom=0.015, wspace=0.03, hspace=0.08)
    fig.savefig(OUT, dpi=160, facecolor="white")
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
