from __future__ import annotations

import re
from pathlib import Path


DOCUMENT = Path(r"D:\fzyc\work\chinese_tnr_figures_20260718\word\document.xml")


def main() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\s*<a:extLst>\s*<a:ext uri=\"\{96DAC541-7B7A-43D3-8B79-37D633B846F1\}\">"
        r"\s*<asvg:svgBlip\b[^>]*/>\s*</a:ext>\s*</a:extLst>",
        flags=re.S,
    )
    updated, count = pattern.subn("", text)
    if count != 7:
        raise RuntimeError(f"Expected seven active SVG extensions, removed {count}")
    DOCUMENT.write_text(updated, encoding="utf-8")
    print(f"Removed {count} SVG rendering extensions; high-resolution PNG fallbacks are now active.")


if __name__ == "__main__":
    main()
