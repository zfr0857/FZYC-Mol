from __future__ import annotations

import zipfile
from copy import copy
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
DOCX_IN = OUT / "小论文-13_Nature格式终审_图1更新.docx"
DOCX_OUT = OUT / "小论文-13_Nature格式终审_图1题名更新.docx"

OLD_TITLE = "候选池扩张增加分子性质预测中的选择损失"
NEW_TITLE = "冻结验证揭示分子性质预测中候选池扩张的收益与选择损失"


def replace_text(data: bytes) -> tuple[bytes, int]:
    text = data.decode("utf-8")
    count = text.count(OLD_TITLE)
    if count:
        text = text.replace(OLD_TITLE, NEW_TITLE)
    return text.encode("utf-8"), count


def main() -> None:
    total = 0
    touched = []
    targets = {"word/document.xml", "docProps/core.xml", "docProps/app.xml"}

    with zipfile.ZipFile(DOCX_IN, "r") as zin:
        with zipfile.ZipFile(DOCX_OUT, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                item = copy(info)
                data = zin.read(info.filename)
                if info.filename in targets:
                    data, count = replace_text(data)
                    if count:
                        total += count
                        touched.append(info.filename)
                zout.writestr(item, data)

    if total == 0:
        raise RuntimeError("Old title was not found in the source document")

    with zipfile.ZipFile(DOCX_OUT, "r") as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP member after write: {bad}")
        ET.fromstring(z.read("word/document.xml"))
        if "docProps/core.xml" in z.namelist():
            ET.fromstring(z.read("docProps/core.xml"))

    print(f"output={DOCX_OUT}")
    print(f"replacements={total}")
    print("touched=" + ",".join(touched))
    print(f"title={NEW_TITLE}")


if __name__ == "__main__":
    main()
