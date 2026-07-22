from pathlib import Path

import build_small_paper4_redline as redline


ROOT = Path(__file__).resolve().parents[1]
redline.ORIGINAL = ROOT / "output" / "小论文-4.docx"
redline.REVISED = ROOT / "output" / "小论文-5.docx"
redline.OUTPUT = ROOT / "output" / "小论文-5_修订痕迹.docx"


if __name__ == "__main__":
    print(redline.build())
