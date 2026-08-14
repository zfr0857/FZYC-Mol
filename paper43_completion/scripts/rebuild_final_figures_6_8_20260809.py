from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import cairosvg
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lxml import etree
from matplotlib.lines import Line2D
from PIL import Image


ROOT = Path(os.environ.get("FZYC_ROOT", r"D:\fzyc"))
PACKAGE = ROOT / "output" / "Journal_of_Cheminformatics_strict_submission_20260809"
OUT = PACKAGE / "03_Figures"
TEMP = ROOT / "work" / "final_figure_revisions_20260809"
SOURCE = PACKAGE / "04_Audits_and_source_data" / "machine_readable_source_tables" / "main_figures"
OLD_SOURCE = ROOT / "output" / "paper43_jcheminform_completion_20260726" / "source_data"
STRUCTURAL = ROOT / "work" / "af4_r12_6_1" / "paper43_completion" / "scripts" / "r11_final" / "build_paper43_r11_structural_figures_20260731.py"
ROUND2 = ROOT / "work" / "build_round2_figures6_8_20260809.py"

BLUE, ORANGE, TEAL, PURPLE = "#3B6EA8", "#D4813A", "#2A8C82", "#8064A2"
GREY, LIGHT, INK = "#7A7F87", "#E6E9EC", "#202830"
DISPLAY = {
    "bace": "BACE", "bbbp": "BBBP", "clintox": "ClinTox",
    "tdc_hia_hou": "HIA", "tdc_pgp_broccatelli": "P-gp",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def setup() -> None:
    mpl.rcParams.update({
        "font.family": "Times New Roman", "font.serif": ["Times New Roman"],
        "font.size": 9, "axes.titlesize": 10.2, "axes.titleweight": "bold",
        "axes.labelsize": 9.2, "xtick.labelsize": 8.2, "ytick.labelsize": 8.2,
        "legend.fontsize": 8.0, "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "mathtext.fontset": "custom", "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman:italic", "axes.unicode_minus": False,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })


def save(fig, number: int, directory: Path = OUT) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for text in fig.findobj(match=mpl.text.Text):
        text.set_fontfamily("Times New Roman")
        if text.get_text() and text.get_fontsize() < 8:
            text.set_fontsize(8)
    fig.savefig(directory / f"Figure{number}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(directory / f"Figure{number}.pdf", bbox_inches="tight", facecolor="white")
    png = directory / f"Figure{number}_600dpi.png"
    fig.savefig(png, dpi=600, bbox_inches="tight", facecolor="white")
    with Image.open(png) as image:
        image.convert("RGB").save(png, dpi=(600, 600), compress_level=6)
    plt.close(fig)


def panel_title(fig, spec, letter: str, title: str, y: float) -> None:
    box = spec.get_position(fig)
    fig.text(box.x0, y, f"{letter}  {title}", ha="left", va="bottom",
             fontsize=10.3, fontweight="bold", color="black", family="Times New Roman")


def clean(ax, axis="y") -> None:
    ax.grid(axis=axis, color=LIGHT, lw=0.6)
    ax.set_axisbelow(True)


def figure6() -> None:
    module = load_module(STRUCTURAL, "final_structural")
    module.setup()
    module.OUT = TEMP

    def intercepted_save(fig, _number):
        save(fig, 6)

    module.save = intercepted_save
    module.figure7()


def figure7() -> None:
    fixed = pd.read_csv(OLD_SOURCE / "fixed_reference_units.csv")
    epsilon = pd.read_csv(OLD_SOURCE / "epsilon_near_equivalence_units.csv")
    comparisons = pd.read_csv(SOURCE / "classification_metric_selector_comparisons_final.csv")
    ks = [4, 8, 16, 32]
    working = epsilon[
        ((epsilon.task_type == "classification") & (epsilon.epsilon == 0.010))
        | ((epsilon.task_type == "regression") & (epsilon.epsilon == 0.050))
    ]

    fig = plt.figure(figsize=(7.2, 5.65))
    gs = fig.add_gridspec(2, 2, left=.105, right=.985, bottom=.09, top=.89,
                          hspace=.34, wspace=.35)
    top_y = .955
    lower_y = gs[1, 0].get_position(fig).y1 + .022

    # A: two task-specific natural scales inside one panel.
    panel_title(fig, gs[0, 0], "A", "Reference and opportunity gaps", top_y)
    asub = gs[0, 0].subgridspec(2, 1, hspace=.28)
    estimates = [
        ("fixed_k32_gap", "-", "K-invariant"),
        ("k_dependent_crossfit_gap", "--", "K-dependent"),
        ("same_fold_opportunity_gap", ":", "Same-fold"),
    ]
    for index, (task, colour, marker, ylabel) in enumerate([
        ("classification", BLUE, "o", "ROC-AUC gap"),
        ("regression", ORANGE, "s", "RMSE gap"),
    ]):
        ax = fig.add_subplot(asub[index])
        part = fixed[fixed.task_type.eq(task)]
        for column, linestyle, label in estimates:
            values = part.groupby("pool_size")[column].mean().reindex(ks)
            ax.plot(values.index, values, color=colour, marker=marker, linestyle=linestyle,
                    lw=1.15, ms=3.5, label=label)
        ax.axhline(0, color=GREY, lw=.75)
        ax.set(xticks=ks, ylabel=ylabel)
        if index == 0:
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("Candidate count, K")
        clean(ax)
    fig.legend(
        handles=[Line2D([0], [0], color=BLUE, linestyle=style, marker="o", label=label)
                 for _column, style, label in estimates],
        frameon=False, ncol=3, fontsize=7.5, loc="upper left",
        bbox_to_anchor=(gs[0, 0].get_position(fig).x0 + .035, .925),
    )

    # B: practical-equivalence success.
    panel_title(fig, gs[0, 1], "B", "Practical-equivalence success", top_y)
    ax = fig.add_subplot(gs[0, 1])
    for task, label, colour, marker in [
        ("classification", "Classification", BLUE, "o"),
        ("regression", "Regression", ORANGE, "s"),
    ]:
        values = working[working.task_type.eq(task)].groupby("pool_size")["crossfit_epsilon_success"].mean().reindex(ks)
        ax.plot(values.index, 100 * values, color=colour, marker=marker, lw=1.2, label=label)
    ax.set(xticks=ks, xlabel="Candidate count, K", ylabel="Success (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, loc="lower right")
    clean(ax)

    # C: near-equivalent candidate sets.
    panel_title(fig, gs[1, 0], "C", "Near-equivalent candidate sets", lower_y)
    ax = fig.add_subplot(gs[1, 0])
    for task, label, colour, marker in [
        ("classification", "Classification", BLUE, "o"),
        ("regression", "Regression", ORANGE, "s"),
    ]:
        values = working[working.task_type.eq(task)].groupby("pool_size")["crossfit_near_equivalent_n"].mean().reindex(ks)
        ax.plot(values.index, values, color=colour, marker=marker, lw=1.2, label=label)
    ax.set(xticks=ks, xlabel="Candidate count, K", ylabel="Mean set size")
    ax.set_ylim(bottom=0)
    clean(ax)

    # D: one merged panel with two independently scaled columns.
    panel_title(fig, gs[1, 1], "D", "PR-AUC versus ROC-AUC selection", lower_y)
    endpoints = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    k32 = comparisons[
        comparisons.pool_size.eq(32) & comparisons.alternative_selector.eq("pr_auc")
    ].groupby("dataset").mean(numeric_only=True).reindex(endpoints)
    switching = (100 * k32.candidate_changed_vs_roc.to_numpy())[:, None]
    effects = k32.delta_outer_pr_auc_vs_roc_selector.to_numpy()[:, None]
    dsub = gs[1, 1].subgridspec(1, 2, wspace=.28)
    definitions = [
        (switching, "Switch", "Blues", (0, 100), "{:.0f}%"),
        (effects, "Outer ΔPR-AUC", "RdBu_r", (-.04, .04), "{:+.3f}"),
    ]
    for index, (array, xlabel, cmap, limits, formatter) in enumerate(definitions):
        ax = fig.add_subplot(dsub[index])
        mesh = ax.pcolormesh(np.arange(2), np.arange(6), array, shading="flat",
                             cmap=cmap, vmin=limits[0], vmax=limits[1])
        ax.set(xlim=(0, 1), ylim=(5, 0))
        ax.set_xticks([.5], [xlabel])
        ax.set_yticks(np.arange(5) + .5, [DISPLAY[x] for x in endpoints] if index == 0 else [])
        if index == 1:
            ax.tick_params(axis="y", left=False, labelleft=False)
        for row in range(5):
            rgba = mesh.cmap(mesh.norm(array[row, 0]))
            luminance = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
            ax.text(.5, row + .5, formatter.format(array[row, 0]), ha="center", va="center",
                    fontsize=8, color="white" if luminance < .5 else "black")
        for spine in ax.spines.values():
            spine.set_visible(False)
    save(fig, 7)


def figure8() -> None:
    module = load_module(ROUND2, "round2_reliability")
    module.OUT = TEMP

    def black_label(ax, letter, title):
        # Use one baseline and one text object so A-D and their titles cannot drift.
        ax.text(-.10, 1.065, f"{letter}  {title}", transform=ax.transAxes,
                fontsize=10.2, fontweight="bold", color="black", va="bottom",
                ha="left", family="Times New Roman")

    def intercepted_save(fig, _number):
        for ax in fig.axes:
            labels = [tick.get_text() for tick in ax.get_xticklabels()]
            if "ChemBERTa" in labels and "MolFormer" in labels:
                ax.tick_params(axis="x", labelrotation=18)
                for tick in ax.get_xticklabels():
                    tick.set_ha("right")
            if ax.get_xlabel() == "Novel / seen-or-related scaffold ratio":
                ticks = [value for value in (.25, .5, 1, 2, 4) if ax.get_xlim()[0] <= value <= ax.get_xlim()[1]]
                ax.set_xticks(ticks)
                ax.set_xticklabels([f"{value:g}" for value in ticks])
        save(fig, 8)

    module.label = black_label
    module.save = intercepted_save
    module.figure6()


def normalize_svg_fonts_and_panel_labels() -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    for number in range(1, 9):
        path = OUT / f"Figure{number}.svg"
        tree = etree.parse(str(path), parser)
        for element in tree.getroot().iter():
            if not isinstance(element.tag, str):
                continue
            if etree.QName(element).localname not in {"text", "tspan"}:
                continue
            style = element.get("style", "")
            style = re.sub(r"font-family:\s*'[^']+'", "font-family: 'Times New Roman'", style)
            style = re.sub(r"font-family:\s*[^;]+", "font-family: 'Times New Roman'", style)
            if number > 1 and etree.QName(element).localname == "text":
                visible = "".join(element.itertext()).strip()
                if visible in {"A", "B", "C", "D", "E"}:
                    if "fill:" in style:
                        style = re.sub(r"fill:\s*#[0-9A-Fa-f]{6}", "fill: #000000", style)
                    else:
                        style += "; fill: #000000"
            element.set("style", style)
        tree.write(str(path), encoding="utf-8", xml_declaration=True,
                   doctype='<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
        svg = path.read_bytes()
        cairosvg.svg2pdf(bytestring=svg, write_to=str(OUT / f"Figure{number}.pdf"))
        png = OUT / f"Figure{number}_600dpi.png"
        cairosvg.svg2png(bytestring=svg, write_to=str(png), scale=600 / 72)
        with Image.open(png) as image:
            image.convert("RGB").save(png, dpi=(600, 600), optimize=True)


if __name__ == "__main__":
    setup()
    TEMP.mkdir(parents=True, exist_ok=True)
    figure6()
    figure7()
    figure8()
    normalize_svg_fonts_and_panel_labels()
    print(OUT)
