from pathlib import Path

from PIL import Image


FIG = Path(r"D:\fzyc\output\paper28_pre_submission_minor_revision_20260717\main_figures")


def main() -> None:
    for path in FIG.glob("*.png"):
        image = Image.open(path).convert("RGB")
        if image.width > 4700:
            height = round(image.height * 4600 / image.width)
            image = image.resize((4600, height), Image.Resampling.LANCZOS)
        image.save(path, format="PNG", dpi=(600, 600), optimize=True)


if __name__ == "__main__":
    main()
