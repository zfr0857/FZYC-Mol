from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path


UNPACKED = Path(r"D:\fzyc\work\chinese_tnr_figures_20260718")
MEDIA = UNPACKED / "word" / "media"
SOURCE = Path(r"D:\fzyc\output\paper30_submission_package_20260717\main_figures")
FIGURE7 = Path(
    r"D:\fzyc\output\paper32_equation_table_format_20260718\main_figures\Figure7_final_requested.svg"
)
SOURCES = [SOURCE / f"Figure{i}.svg" for i in range(1, 7)] + [FIGURE7]
TARGETS = [MEDIA / f"image{i}.svg" for i in range(2, 15, 2)]
PNG_SOURCES = [SOURCE / f"Figure{i}_600dpi.png" for i in range(1, 7)] + [
    Path(
        r"D:\fzyc\output\paper32_equation_table_format_20260718\main_figures\Figure7_final_requested_1200dpi.png"
    )
]
PNG_TARGETS = [MEDIA / f"image{i}.png" for i in range(1, 14, 2)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def families(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    explicit = re.findall(
        r"font-family\s*:\s*([^;\"}]+)|font-family\s*=\s*[\"']([^\"']+)",
        text,
        flags=re.I,
    )
    shorthand = re.findall(
        r"(?:^|[;\"]\s*)font\s*:\s*[^;]*?[\"']([^\"']+)[\"']",
        text,
        flags=re.I,
    )
    values = {(left or right).strip().strip("'\"") for left, right in explicit}
    values.update(value.strip() for value in shorthand)
    return values


def main() -> None:
    for figure, (source, target) in enumerate(zip(SOURCES, TARGETS), start=1):
        source_families = families(source)
        if source_families != {"Times New Roman"}:
            raise RuntimeError(f"Figure {figure} source fonts: {sorted(source_families)}")
        shutil.copyfile(source, target)
        if sha256(source) != sha256(target):
            raise RuntimeError(f"Figure {figure} copy verification failed")
        print(f"Figure {figure}: {target.name} {sha256(target)}")
    for figure, (source, target) in enumerate(zip(PNG_SOURCES, PNG_TARGETS), start=1):
        shutil.copyfile(source, target)
        if sha256(source) != sha256(target):
            raise RuntimeError(f"Figure {figure} PNG fallback copy verification failed")
        print(f"Figure {figure} fallback: {target.name} {sha256(target)}")


if __name__ == "__main__":
    main()
