from __future__ import annotations

import io
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from PIL import Image
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"
PACKAGE_MAIN = ROOT / "reports" / "submission_package" / "main_figures"
PACKAGE_SUPP = ROOT / "reports" / "submission_package" / "supplementary_figures"


COL = {
    "ink": "#111827",
    "muted": "#667085",
    "line": "#7a7a7a",
    "dash": "#4b5563",
    "blue": "#2f6fed",
    "cyan": "#0891b2",
    "green": "#15803d",
    "teal": "#0f766e",
    "orange": "#c05a00",
    "amber": "#b7791f",
    "purple": "#7c3aed",
    "rose": "#be123c",
    "gray": "#475467",
    "soft_blue": "#eaf5ff",
    "soft_cyan": "#e7fbff",
    "soft_green": "#eaf8ec",
    "soft_mint": "#edfff3",
    "soft_orange": "#fff1e7",
    "soft_amber": "#fff8df",
    "soft_purple": "#f2edff",
    "soft_rose": "#fff0f2",
    "soft_gray": "#f5f6f8",
}

EXAMPLE_SMILES = "O=C(Nc1ccccc1)c1ccncc1"


def setup() -> None:
    for font_path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/arial.ttf")]:
        if font_path.exists():
            fm.fontManager.addfont(str(font_path))
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.unicode_minus": False,
            "figure.dpi": 160,
            "savefig.dpi": 360,
        }
    )


def add_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str = "",
    body: list[str] | None = None,
    fc: str = "white",
    ec: str = COL["line"],
    lw: float = 1.3,
    radius: float = 0.022,
    ls: str = "-",
    title_size: float = 8.5,
    body_size: float = 6.5,
    pad: float = 0.014,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.010,rounding_size={radius}",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        linestyle=ls,
    )
    ax.add_patch(patch)
    if title:
        ax.text(x + pad, y + h - 0.025, title, ha="left", va="top", fontsize=title_size, fontweight="bold", color=COL["ink"])
    if body:
        ax.text(
            x + pad,
            y + h - 0.058,
            "\n".join(body),
            ha="left",
            va="top",
            fontsize=body_size,
            linespacing=1.2,
            color=COL["muted"],
        )
    return patch


def arrow(ax, start: tuple[float, float], end: tuple[float, float], color: str = COL["dash"], lw: float = 1.25, dashed: bool = False, rad: float = 0.0) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=lw,
            color=color,
            linestyle="--" if dashed else "-",
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=2,
            shrinkB=2,
        )
    )


def panel_label(ax, x: float, y: float, text: str, size: float = 10.8) -> None:
    ax.text(x, y, text, ha="left", va="top", fontsize=size, fontweight="bold", color=COL["ink"])


def rdkit_molecule_image(width: int = 900, height: int = 620) -> Image.Image:
    mol = Chem.MolFromSmiles(EXAMPLE_SMILES)
    if mol is None:
        raise ValueError("Invalid example SMILES")
    AllChem.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DCairo(width, height)
    options = drawer.drawOptions()
    options.clearBackground = False
    options.padding = 0.055
    options.bondLineWidth = 2.4
    options.minFontSize = 16
    options.maxFontSize = 28
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    img = Image.open(io.BytesIO(drawer.GetDrawingText())).convert("RGBA")
    # Keep the molecule crisp on any panel background by removing RDKit's near-white canvas.
    data = []
    pixels = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    for r, g, b, a in pixels:
        if r > 247 and g > 247 and b > 247:
            data.append((255, 255, 255, 0))
        else:
            data.append((r, g, b, a))
    img.putdata(data)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        pad = 28
        padded = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (255, 255, 255, 0))
        padded.paste(img, (pad, pad))
        img = padded
    return img


def add_rdkit_molecule(ax, x: float, y: float, w: float, h: float, zorder: int = 4) -> None:
    img = rdkit_molecule_image()
    ax.imshow(img, extent=(x, x + w, y, y + h), interpolation="lanczos", zorder=zorder, aspect="auto")
    ax.set_aspect("auto")


def molecule(ax, cx: float, cy: float, s: float = 1.0, color: str = COL["ink"]) -> None:
    # A compact fused-ring-like schematic, drawn as line art.
    r = 0.030 * s
    pts = []
    for i in range(6):
        a = math.pi / 6 + i * math.pi / 3
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(6):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % 6]
        ax.plot([x1, x2], [y1, y2], color=color, lw=1.4)
    tail = [(cx + 0.026 * s, cy + 0.010 * s), (cx + 0.055 * s, cy + 0.025 * s), (cx + 0.073 * s, cy - 0.006 * s), (cx + 0.047 * s, cy - 0.030 * s)]
    for p, q in zip(tail, tail[1:]):
        ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=1.4)
    ax.text(cx - 0.003 * s, cy + 0.054 * s, "O", fontsize=9 * s, fontweight="bold", ha="center", va="center", color=color)
    ax.text(cx + 0.079 * s, cy - 0.004 * s, "N", fontsize=9 * s, fontweight="bold", ha="center", va="center", color=color)


def graph_icon(ax, x: float, y: float, w: float, h: float, accent: str = COL["blue"], n: int = 9) -> None:
    coords = [
        (x + 0.18 * w, y + 0.28 * h),
        (x + 0.34 * w, y + 0.62 * h),
        (x + 0.52 * w, y + 0.48 * h),
        (x + 0.70 * w, y + 0.70 * h),
        (x + 0.78 * w, y + 0.34 * h),
        (x + 0.56 * w, y + 0.20 * h),
        (x + 0.36 * w, y + 0.24 * h),
        (x + 0.20 * w, y + 0.72 * h),
        (x + 0.65 * w, y + 0.47 * h),
    ][:n]
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 0), (1, 7), (2, 8), (8, 4)]
    for i, j in edges:
        if i < len(coords) and j < len(coords):
            ax.plot([coords[i][0], coords[j][0]], [coords[i][1], coords[j][1]], color="#475569", lw=1.0, alpha=0.85)
    for k, (px, py) in enumerate(coords):
        fc = accent if k % 3 == 0 else ("#ffffff" if k % 3 == 1 else "#a7d8ff")
        ax.add_patch(Circle((px, py), 0.012 * min(w / 0.16, h / 0.12), facecolor=fc, edgecolor="#1f2937", lw=1.0))


def feature_bar(ax, x: float, y: float, w: float, h: float, colors: list[str] | None = None, n: int = 8, outline: bool = True) -> None:
    colors = colors or ["#8ecae6", "#ffffff", "#ffb703", "#bde0fe", "#caffbf", "#ffffff", "#ffadad", "#d8f3dc"]
    cell = w / n
    for i in range(n):
        ax.add_patch(Rectangle((x + i * cell, y), cell * 0.88, h, facecolor=colors[i % len(colors)], edgecolor="#344054" if outline else "none", lw=0.7))
    if outline:
        ax.add_patch(Rectangle((x, y), w, h, facecolor="none", edgecolor="#1f2937", lw=1.0))


def feature_stack(ax, x: float, y: float, w: float, h: float, rows: int = 5) -> None:
    labels = ["Morgan", "MACCS", "AtomPairs", "PhysChem", "Pretrained"]
    cols = ["#ff4d4f", "#5b8def", "#b6c2cc", "#f4a261", "#9be28b"]
    row_h = h / rows
    label_w = min(0.055, w * 0.50)
    bit_step = (w - label_w) / 5
    bit_w = bit_step * 0.72
    for i in range(rows):
        yy = y + (rows - 1 - i) * row_h
        ax.text(x, yy + row_h * 0.45, labels[i], fontsize=5.6, ha="left", va="center", color=COL["ink"])
        for j in range(5):
            ax.add_patch(
                Rectangle(
                    (x + label_w + j * bit_step, yy + row_h * 0.22),
                    bit_w,
                    row_h * 0.56,
                    facecolor=cols[i],
                    edgecolor="white",
                    lw=0.3,
                    alpha=0.9,
                )
            )


def encoder_wedge(ax, x: float, y: float, w: float, h: float, label: str, fc: str = "#ffe2cf") -> None:
    poly = Polygon([(x, y), (x + w, y + h * 0.18), (x + w, y + h * 0.82), (x, y + h)], closed=True, facecolor=fc, edgecolor=COL["line"], lw=1.1)
    ax.add_patch(poly)
    ax.text(x + w * 0.52, y + h * 0.50, label, ha="center", va="center", fontsize=7.0, color=COL["ink"], fontweight="bold")


def mini_matrix(ax, x: float, y: float, w: float, h: float, rows: int = 5, cols: int = 7) -> None:
    palette = ["#c7d2fe", "#bfdbfe", "#bbf7d0", "#fed7aa", "#fecdd3", "#ffffff"]
    cw = w / cols
    rh = h / rows
    for r in range(rows):
        for c in range(cols):
            ax.add_patch(Rectangle((x + c * cw, y + r * rh), cw * 0.88, rh * 0.82, facecolor=palette[(r + c) % len(palette)], edgecolor="#475569", lw=0.35))
    ax.add_patch(Rectangle((x, y), w, h, facecolor="none", edgecolor="#1f2937", lw=0.9))


def draw_overall_workflow() -> None:
    setup()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_MAIN.mkdir(parents=True, exist_ok=True)
    PACKAGE_SUPP.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(16.5, 9.4))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.965, "FZYC-Mol overall workflow", ha="center", va="top", fontsize=18.0, fontweight="bold", color=COL["ink"])
    ax.text(0.5, 0.925, "Multi-view molecular encoding, validation-governed expert selection, and reliability-aware ADMET reporting", ha="center", va="top", fontsize=10.0, color=COL["muted"])

    add_box(ax, 0.035, 0.215, 0.150, 0.620, "", fc="white", ec="none", lw=0)
    add_box(ax, 0.040, 0.520, 0.140, 0.185, "2D molecule", [], fc="white", ec="#d0d5dd", lw=1.25, radius=0.018, title_size=7.4)
    add_rdkit_molecule(ax, 0.049, 0.548, 0.122, 0.112)
    ax.text(0.110, 0.498, "Input molecule", ha="center", fontsize=8.5, fontweight="bold", color=COL["ink"])
    add_box(ax, 0.052, 0.300, 0.115, 0.120, "Benchmarks", ["MoleculeNet", "TDC ADMET", "MoleculeACE", "OpenADMET"], fc=COL["soft_gray"], ec="#cbd5e1", title_size=7.8, body_size=6.0)

    add_box(ax, 0.205, 0.175, 0.255, 0.680, "", fc=COL["soft_cyan"], ec=COL["cyan"], lw=1.8, radius=0.030)
    panel_label(ax, 0.220, 0.835, "a  Multi-view generation")
    sub = [
        (0.232, 0.655, "Atom graph", COL["soft_blue"], COL["blue"]),
        (0.232, 0.475, "Bond graph", COL["soft_green"], COL["green"]),
        (0.232, 0.295, "Fingerprint bank", COL["soft_orange"], COL["orange"]),
        (0.345, 0.295, "Descriptor / embedding", COL["soft_purple"], COL["purple"]),
    ]
    for x, y, t, fc, ec in sub:
        add_box(ax, x, y, 0.095, 0.120, t, [], fc=fc, ec=ec, title_size=7.2, body_size=5.5, radius=0.018)
    graph_icon(ax, 0.242, 0.672, 0.075, 0.070, COL["blue"], n=8)
    graph_icon(ax, 0.242, 0.492, 0.075, 0.070, COL["green"], n=7)
    feature_stack(ax, 0.245, 0.312, 0.085, 0.070, rows=5)
    encoder_wedge(ax, 0.363, 0.317, 0.037, 0.065, "enc", fc="#f6d7ff")
    feature_bar(ax, 0.410, 0.334, 0.040, 0.032, n=5)
    for yy in [0.720, 0.540, 0.350]:
        arrow(ax, (0.178, 0.610), (0.220, yy), dashed=True, lw=1.1)

    add_box(ax, 0.500, 0.175, 0.285, 0.680, "", fc=COL["soft_green"], ec=COL["green"], lw=1.8, radius=0.030)
    panel_label(ax, 0.515, 0.835, "b  Expert pool + selector")
    expert_specs = [
        (0.525, 0.650, "I  Graph", [], COL["soft_blue"], COL["blue"]),
        (0.640, 0.650, "II  Fingerprint", [], COL["soft_orange"], COL["orange"]),
        (0.525, 0.465, "III  Encoder", [], COL["soft_purple"], COL["purple"]),
        (0.640, 0.465, "IV  Ensemble", [], COL["soft_rose"], COL["rose"]),
    ]
    for x, y, t, lines, fc, ec in expert_specs:
        add_box(ax, x, y, 0.100, 0.125, t, lines, fc=fc, ec=ec, title_size=7.1, body_size=5.7, radius=0.018)
    graph_icon(ax, 0.538, 0.662, 0.070, 0.052, COL["blue"], n=6)
    ax.text(0.574, 0.662, "GIN / D-MPNN", fontsize=5.6, color=COL["muted"], ha="center", va="bottom")
    for i in range(3):
        feature_bar(ax, 0.657, 0.684 - i * 0.018, 0.070, 0.013, n=7, outline=True)
    ax.text(0.692, 0.660, "RF / GBDT", fontsize=5.6, color=COL["muted"], ha="center", va="bottom")
    encoder_wedge(ax, 0.545, 0.495, 0.035, 0.060, "E", fc="#f6d7ff")
    feature_bar(ax, 0.590, 0.515, 0.035, 0.023, n=5)
    ax.text(0.584, 0.492, "frozen + 3D", fontsize=5.5, color=COL["muted"], ha="center", va="bottom")
    mini_matrix(ax, 0.661, 0.500, 0.055, 0.043, rows=4, cols=6)
    ax.text(0.690, 0.493, "Top-K / stacking", fontsize=5.5, color=COL["muted"], ha="center", va="bottom")
    add_box(ax, 0.545, 0.255, 0.190, 0.115, "Validation selector", [], fc="#f7f2ff", ec=COL["purple"], title_size=8.0, body_size=6.0, lw=1.7)
    mini_matrix(ax, 0.557, 0.282, 0.055, 0.042, rows=4, cols=6)
    ax.text(0.625, 0.316, "endpoint metric", fontsize=5.9, color=COL["muted"], ha="left", va="center")
    ax.text(0.625, 0.299, "risk-adjusted mean", fontsize=5.9, color=COL["muted"], ha="left", va="center")
    ax.text(0.625, 0.282, "retained-best gate", fontsize=5.9, color=COL["muted"], ha="left", va="center")
    feature_bar(ax, 0.687, 0.286, 0.040, 0.026, n=5)
    ax.text(0.733, 0.300, "best", fontsize=6.8, fontweight="bold", color=COL["purple"], ha="left", va="center")
    for x0 in [0.575, 0.690]:
        arrow(ax, (x0, 0.650), (0.635, 0.370), color=COL["purple"], dashed=True, lw=1.0)
        arrow(ax, (x0, 0.465), (0.635, 0.370), color=COL["purple"], dashed=True, lw=1.0)

    add_box(ax, 0.825, 0.175, 0.145, 0.680, "", fc=COL["soft_gray"], ec="#94a3b8", lw=1.8, radius=0.030)
    panel_label(ax, 0.840, 0.835, "c  Evidence outputs")
    out_specs = [
        (0.846, 0.680, "Property", ["classification", "regression"], COL["soft_green"], COL["green"]),
        (0.846, 0.550, "Reliability", ["uncertainty", "risk coverage"], COL["soft_blue"], COL["blue"]),
        (0.846, 0.420, "AD / OOD", ["Tanimoto", "reconstruction"], COL["soft_cyan"], COL["cyan"]),
        (0.846, 0.290, "Interpretability", ["motifs", "case studies"], COL["soft_amber"], COL["amber"]),
    ]
    for x, y, t, lines, fc, ec in out_specs:
        add_box(ax, x, y, 0.100, 0.090, t, lines, fc=fc, ec=ec, title_size=7.6, body_size=5.8, radius=0.016)
    for yy in [0.725, 0.595, 0.465, 0.335]:
        arrow(ax, (0.738, 0.312), (0.840, yy), color=COL["green"], lw=1.15, rad=0.04)

    arrow(ax, (0.460, 0.515), (0.500, 0.515), dashed=True, lw=1.2)
    arrow(ax, (0.785, 0.312), (0.825, 0.515), dashed=True, lw=1.2)

    add_box(ax, 0.055, 0.045, 0.890, 0.100, "Experiment-thickening layer", [], fc="#f8fafc", ec="#cbd5e1", title_size=8.2, radius=0.020)
    pills = [
        ("external benchmark", 0.225, COL["soft_blue"]),
        ("calibration / imbalance", 0.375, COL["soft_cyan"]),
        ("Top-K / stacking", 0.545, COL["soft_green"]),
        ("roughness audit", 0.695, COL["soft_amber"]),
        ("negative results retained", 0.835, COL["soft_rose"]),
    ]
    for text, cx, fc in pills:
        add_box(ax, cx - 0.062, 0.070, 0.124, 0.036, "", [], fc=fc, ec="none", title_size=6.6, radius=0.014, pad=0.005)
        ax.text(cx, 0.088, text, ha="center", va="center", fontsize=6.5, fontweight="bold", color=COL["ink"])

    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"fig1_framework_overview_polished.{ext}", bbox_inches="tight", facecolor="white")
        fig.savefig(PACKAGE_MAIN / f"Figure_1_FZYC_Mol_framework.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def draw_model_structure() -> None:
    setup()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_SUPP.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(16.5, 9.3))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.965, "FZYC-Mol model structure", ha="center", va="top", fontsize=18.0, fontweight="bold", color=COL["ink"])
    ax.text(0.5, 0.925, "Parallel molecular experts are fused only through validation evidence, then exported with uncertainty, AD/OOD, and interpretation signals.", ha="center", va="top", fontsize=9.8, color=COL["muted"])

    add_box(ax, 0.045, 0.165, 0.205, 0.720, "", fc=COL["soft_blue"], ec="#9cc8e5", lw=1.7, radius=0.030)
    panel_label(ax, 0.062, 0.865, "A  Molecular view generator", size=11.0)
    add_box(ax, 0.078, 0.700, 0.140, 0.110, "2D molecule", [], fc="white", ec="#a3a3a3", title_size=7.6)
    add_rdkit_molecule(ax, 0.092, 0.718, 0.112, 0.066)
    add_box(ax, 0.078, 0.520, 0.140, 0.125, "Heterogeneous graph", [], fc="white", ec="#9ca3af", title_size=7.4, ls="--")
    graph_icon(ax, 0.100, 0.542, 0.090, 0.070, COL["blue"], n=8)
    add_box(ax, 0.078, 0.335, 0.140, 0.125, "Molecular feature bank", [], fc="white", ec="#9ca3af", title_size=7.4, ls="--")
    feature_stack(ax, 0.096, 0.356, 0.120, 0.070, rows=5)
    arrow(ax, (0.137, 0.700), (0.137, 0.645), lw=1.0)
    arrow(ax, (0.137, 0.520), (0.137, 0.460), lw=1.0)

    add_box(ax, 0.285, 0.535, 0.415, 0.350, "", fc="#fff0e6", ec="#e2b49a", lw=1.7, radius=0.026)
    panel_label(ax, 0.305, 0.865, "B  Expert encoding modules", size=11.0)
    add_box(ax, 0.310, 0.700, 0.150, 0.095, "I  Graph message passing", [], fc=COL["soft_blue"], ec=COL["blue"], title_size=7.2, body_size=5.7)
    graph_icon(ax, 0.325, 0.713, 0.085, 0.046, COL["blue"], n=6)
    ax.text(0.385, 0.711, "GIN / D-MPNN", ha="center", va="center", fontsize=5.7, color=COL["muted"])
    add_box(ax, 0.485, 0.700, 0.160, 0.095, "II  Fingerprint sensing", [], fc=COL["soft_orange"], ec=COL["orange"], title_size=7.2, body_size=5.7)
    feature_stack(ax, 0.505, 0.714, 0.115, 0.043, rows=5)
    add_box(ax, 0.310, 0.590, 0.150, 0.085, "III  Descriptor trees", [], fc=COL["soft_green"], ec=COL["green"], title_size=7.2, body_size=5.7)
    mini_matrix(ax, 0.328, 0.602, 0.060, 0.026, rows=4, cols=7)
    ax.text(0.395, 0.606, "RF / GBDT", ha="center", va="center", fontsize=5.4, color=COL["muted"])
    add_box(ax, 0.485, 0.590, 0.160, 0.085, "IV  Frozen encoders", [], fc=COL["soft_purple"], ec=COL["purple"], title_size=7.2, body_size=5.7)
    encoder_wedge(ax, 0.508, 0.600, 0.033, 0.035, "E", fc="#e9d5ff")
    feature_bar(ax, 0.555, 0.610, 0.056, 0.018, n=7)
    ax.text(0.566, 0.598, "ChemBERTa / MoLFormer", ha="center", va="center", fontsize=5.2, color=COL["muted"])

    add_box(ax, 0.285, 0.165, 0.415, 0.355, "", fc="#eaffea", ec="#9ccf9e", lw=1.7, radius=0.026)
    panel_label(ax, 0.305, 0.500, "C  Validation selector and fusion layer", size=11.0)
    add_box(ax, 0.312, 0.360, 0.115, 0.095, "Validation matrix", ["endpoint x seed x expert"], fc="white", ec="#94a3b8", title_size=7.0, body_size=5.4)
    mini_matrix(ax, 0.330, 0.378, 0.065, 0.038, rows=5, cols=7)
    add_box(ax, 0.455, 0.360, 0.120, 0.095, "Risk-aware policy", ["mean -/+ 0.5 SD", "stability tie-breaker"], fc=COL["soft_purple"], ec=COL["purple"], title_size=7.0, body_size=5.4)
    add_box(ax, 0.600, 0.360, 0.075, 0.095, "Gate", ["retained", "best"], fc=COL["soft_rose"], ec=COL["rose"], title_size=7.0, body_size=5.5)
    add_box(ax, 0.375, 0.235, 0.190, 0.085, "Optional validation-only ensemble", ["Top-K probability/mean fusion; ridge/logistic stacking"], fc=COL["soft_cyan"], ec=COL["cyan"], title_size=7.0, body_size=5.4)
    arrow(ax, (0.427, 0.405), (0.455, 0.405), color=COL["purple"], lw=1.1)
    arrow(ax, (0.575, 0.405), (0.600, 0.405), color=COL["purple"], lw=1.1)
    arrow(ax, (0.470, 0.360), (0.470, 0.320), color=COL["cyan"], dashed=True, lw=1.0)
    arrow(ax, (0.565, 0.280), (0.635, 0.360), color=COL["cyan"], dashed=True, lw=1.0)

    for sx, sy in [(0.385, 0.590), (0.565, 0.590), (0.385, 0.535), (0.565, 0.535)]:
        arrow(ax, (sx, sy), (0.370, 0.455), color="#8b5cf6", dashed=True, lw=1.0, rad=0.05)

    add_box(ax, 0.740, 0.165, 0.215, 0.720, "", fc=COL["soft_gray"], ec="#b8c0cc", lw=1.7, radius=0.030)
    panel_label(ax, 0.760, 0.865, "D  Prediction and evidence heads", size=11.0)
    add_box(ax, 0.780, 0.700, 0.140, 0.100, "Property head", ["ROC-AUC / PR-AUC", "RMSE / MAE / Spearman"], fc=COL["soft_green"], ec=COL["green"], title_size=7.4, body_size=5.7)
    add_box(ax, 0.780, 0.565, 0.140, 0.100, "Calibration head", ["Brier / ECE", "conformal coverage"], fc=COL["soft_blue"], ec=COL["blue"], title_size=7.4, body_size=5.7)
    add_box(ax, 0.780, 0.430, 0.140, 0.100, "AD/OOD head", ["Tanimoto distance", "reconstruction error"], fc=COL["soft_cyan"], ec=COL["cyan"], title_size=7.4, body_size=5.7)
    add_box(ax, 0.780, 0.295, 0.140, 0.100, "Explanation head", ["motif attribution", "fragment enrichment"], fc=COL["soft_amber"], ec=COL["amber"], title_size=7.4, body_size=5.7)
    add_box(ax, 0.780, 0.195, 0.140, 0.070, "Report package", ["main tables + appendix"], fc="white", ec="#94a3b8", title_size=7.2, body_size=5.7)
    for yy in [0.750, 0.615, 0.480, 0.345, 0.232]:
        arrow(ax, (0.675, 0.405), (0.780, yy), color=COL["green"], lw=1.15, rad=0.04)

    arrow(ax, (0.218, 0.585), (0.285, 0.720), dashed=True, lw=1.1)
    arrow(ax, (0.218, 0.395), (0.285, 0.630), dashed=True, lw=1.1)
    arrow(ax, (0.218, 0.395), (0.285, 0.405), dashed=True, lw=1.1)

    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"fig23_fzyc_mol_model_structure.{ext}", bbox_inches="tight", facecolor="white")
        fig.savefig(PACKAGE_SUPP / f"Figure_S16_FZYC_Mol_model_structure.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    draw_overall_workflow()
    draw_model_structure()


if __name__ == "__main__":
    main()
