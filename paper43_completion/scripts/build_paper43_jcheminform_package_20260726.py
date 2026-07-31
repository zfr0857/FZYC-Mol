from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(r"D:\fzyc")
OUT = ROOT / "output" / "paper43_jcheminform_completion_20260726"
TABLES = OUT / "additional_files" / "tables"
FIGURES = OUT / "figures"
UPLOAD = OUT / "upload_ready"
AUTHOR_REVIEW = OUT / "author_review"
REPOSITORY = OUT / "repository_deposition"
BASE_MANUSCRIPT = ROOT / "output" / "paper42_methodological_reframe_20260726" / "Main_manuscript_methodologically_reframed_CLEAN_PENDING_AUTHOR_METADATA.docx"
BASE_SUPP_ZIP = ROOT / "output" / "paper37_joc_supplementary_ready_20260723" / "Journal_of_Cheminformatics_supplementary_submission_package_20260723_FINAL.zip"


def find_paragraph(doc: Document, prefix: str):
    for paragraph in doc.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise KeyError(prefix)


def replace_paragraph(doc: Document, prefix: str, text: str) -> None:
    paragraph = find_paragraph(doc, prefix)
    paragraph.text = text


def add_before(target, text: str = "", style: str | None = None):
    paragraph = target.insert_paragraph_before(text)
    if style:
        paragraph.style = style
    return paragraph


def add_picture_before(target, path: Path, width: float = 6.5):
    paragraph = target.insert_paragraph_before()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(path), width=Inches(width))
    return paragraph


def replace_picture_before_caption(doc: Document, caption_prefix: str, path: Path, width: float = 6.5) -> None:
    caption = find_paragraph(doc, caption_prefix)
    paragraphs = doc.paragraphs
    index = next(i for i, paragraph in enumerate(paragraphs) if paragraph._p is caption._p)
    image_paragraph = next(p for p in reversed(paragraphs[:index]) if "w:drawing" in p._p.xml)
    image_paragraph.clear()
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.add_run().add_picture(str(path), width=Inches(width))


def format_effect(value: float, low: float, high: float) -> str:
    return f"{value:.4f} ({low:.4f}, {high:.4f})"


def load_values() -> dict[str, object]:
    contrasts = pd.read_csv(TABLES / "fixed_reference_k32_vs_k4_contrasts.csv")
    fixed = contrasts[contrasts["estimand"].eq("fixed_k32_gap")].copy()
    epsilon = pd.read_csv(TABLES / "epsilon_near_equivalence_units.csv")
    metric = pd.read_csv(TABLES / "classification_metric_selector_comparisons.csv")
    metric_units = pd.read_csv(TABLES / "classification_metric_selection_units.csv")
    controls = pd.read_csv(TABLES / "constructed_candidate_control_units.csv")
    recovery = pd.read_csv(TABLES / "empirical_heteroskedastic_recovery_simulation.csv")
    fits = pd.read_csv(TABLES / "fit_execution_audit.csv")
    rerun_audit = pd.read_csv(TABLES / "legacy_to_current_rerun_audit.csv")
    classification = fixed[fixed["task_type"].eq("classification")]
    regression = fixed[fixed["task_type"].eq("regression")]
    exclude = (fixed["seed_block_interval_low"] > 0) | (fixed["seed_block_interval_high"] < 0)
    working = epsilon[
        ((epsilon["task_type"].eq("classification")) & epsilon["epsilon"].eq(0.01))
        | ((epsilon["task_type"].eq("regression")) & epsilon["epsilon"].eq(0.05))
    ]
    working32 = working[working["pool_size"].eq(32)]
    metric32 = metric[metric["pool_size"].eq(32)]
    selections32 = metric_units[metric_units["pool_size"].eq(32)]
    roc32 = selections32[selections32["selector"].eq("roc_auc")].set_index(["dataset", "seed", "outer_fold"])
    metric_deltas = {}
    for selector in ["pr_auc", "minority_constrained"]:
        alternative = selections32[selections32["selector"].eq(selector)].set_index(["dataset", "seed", "outer_fold"])
        metric_deltas[selector] = (
            alternative[["outer_roc_auc", "outer_pr_auc", "outer_minority_recall", "outer_majority_recall", "outer_minority_miss_rate"]]
            - roc32[["outer_roc_auc", "outer_pr_auc", "outer_minority_recall", "outer_majority_recall", "outer_minority_miss_rate"]]
        ).mean()
    control_summary = controls.groupby(["control", "pool_size"], as_index=False).mean(numeric_only=True)
    rec = recovery[
        recovery["scenario"].eq("empirical_correlation_heteroskedastic")
        & recovery["noise_scale"].eq(1.0)
        & recovery["pool_size"].eq(32)
    ]
    primary_fits = fits[fits["source"].str.startswith("primary_")]
    metric_fits = fits[fits["source"].eq("primary_old_seed_classification_rerun")]
    split_fits = fits[fits["source"].eq("primary_old_seed_regression_split_update")]
    return {
        "fixed": fixed,
        "positive": int((fixed["mean_natural_scale_effect"] > 0).sum()),
        "negative": int((fixed["mean_natural_scale_effect"] < 0).sum()),
        "exclude": int(exclude.sum()),
        "class_range": (classification["mean_natural_scale_effect"].min(), classification["mean_natural_scale_effect"].max()),
        "reg_range": (regression["mean_natural_scale_effect"].min(), regression["mean_natural_scale_effect"].max()),
        "epsilon_success": float(working32["crossfit_epsilon_success"].mean()),
        "epsilon_set": float(working32["crossfit_near_equivalent_n"].mean()),
        "epsilon_selected_in_set": float(working32["selected_in_crossfit_set"].mean()),
        "epsilon_jaccard": float(working32["validation_crossfit_set_jaccard"].mean()),
        "epsilon_by_k": working.groupby("pool_size")[["crossfit_epsilon_success", "crossfit_near_equivalent_n", "selected_in_crossfit_set", "validation_crossfit_set_jaccard"]].mean(),
        "epsilon_grid32": epsilon[epsilon["pool_size"].eq(32)].groupby(["task_type", "epsilon"])[["crossfit_epsilon_success", "crossfit_near_equivalent_n", "selected_in_crossfit_set", "validation_crossfit_set_jaccard"]].mean(),
        "metric32": metric32.groupby("alternative_selector").mean(numeric_only=True),
        "metric_deltas": metric_deltas,
        "minority_inner_eligibility": float(selections32[selections32["selector"].eq("minority_constrained")]["inner_constraint_met"].mean()),
        "minority_outer_satisfaction": float((selections32[selections32["selector"].eq("minority_constrained")]["outer_minority_recall"] >= 0.80).mean()),
        "control_summary": control_summary,
        "recovery32": rec,
        "primary_fits": int(primary_fits["total_fits"].sum()),
        "metric_fits": int(metric_fits["total_fits"].sum()),
        "split_fits": int(split_fits["total_fits"].sum()),
        "fit_seconds": float(primary_fits["summed_fit_seconds"].sum()),
        "classification_rerun_max_difference": float(rerun_audit[rerun_audit["rerun_type"].eq("classification_metric")]["max_abs_outer_utility_difference"].max()),
        "regression_transition_max_difference": float(rerun_audit[rerun_audit["rerun_type"].eq("regression_split_manifest")]["max_abs_outer_utility_difference"].max()),
    }


def set_journal_layout(doc: Document) -> None:
    for style_name in ["Normal", "Body Text"]:
        if style_name in doc.styles:
            style = doc.styles[style_name]
            style.font.name = "Arial"
            style.font.size = Pt(10)
            style.paragraph_format.line_spacing = 2
            style.paragraph_format.space_after = Pt(0)
    for paragraph in doc.paragraphs:
        paragraph.paragraph_format.line_spacing = 2
        ppr = paragraph._p.get_or_add_pPr()
        page_break = ppr.find(qn("w:pageBreakBefore"))
        if page_break is not None:
            ppr.remove(page_break)
        for br in paragraph._p.xpath(".//w:br[@w:type='page']"):
            br.getparent().remove(br)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.line_spacing = 2
                tcpr = cell._tc.get_or_add_tcPr()
                for shading in tcpr.findall(qn("w:shd")):
                    tcpr.remove(shading)
    for section in doc.sections:
        sect = section._sectPr
        for old in sect.findall(qn("w:lnNumType")):
            sect.remove(old)
        line_num = OxmlElement("w:lnNumType")
        line_num.set(qn("w:countBy"), "1")
        line_num.set(qn("w:start"), "1")
        line_num.set(qn("w:restart"), "newPage")
        sect.append(line_num)
        footer = section.footer
        paragraph = footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if "PAGE" not in paragraph._p.xml:
            paragraph.text = ""
            run = paragraph.add_run()
            begin = OxmlElement("w:fldChar")
            begin.set(qn("w:fldCharType"), "begin")
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = " PAGE "
            separate = OxmlElement("w:fldChar")
            separate.set(qn("w:fldCharType"), "separate")
            end = OxmlElement("w:fldChar")
            end.set(qn("w:fldCharType"), "end")
            run._r.extend([begin, instr, separate, end])


def build_main(values: dict[str, object]) -> Path:
    doc = Document(BASE_MANUSCRIPT)
    c_low, c_high = values["class_range"]
    r_low, r_high = values["reg_range"]
    metric = values["metric32"]
    pr = metric.loc["pr_auc"]
    minority = metric.loc["minority_constrained"]
    pr_delta = values["metric_deltas"]["pr_auc"]
    minority_delta = values["metric_deltas"]["minority_constrained"]
    rec = values["recovery32"]

    replace_paragraph(doc, "Opportunity, validation", "Candidate-pool opportunity and selection stability under finite validation in molecular property prediction: a repeated nested audit")
    replace_paragraph(doc, "[AUTHOR NAMES", "[AUTHOR NAMES AND ORCID IDS REQUIRED BEFORE SUBMISSION]")
    replace_paragraph(doc, "Running title:", "Running title: Candidate-pool opportunity under finite validation")
    replace_paragraph(doc, "Background:", "Background: Molecular property-prediction studies compare increasingly large, correlated registries of representations, learners and tuning variants. Expansion can add complementary chemical information, but finite validation data may not rank the enlarged opportunity set reproducibly.")
    replace_paragraph(doc, "Methods:", "Methods: We audited nine public endpoints with 32 registered lightweight candidates, K = 4, 8, 16 and 32, three inner and three outer scaffold folds, and ten split seeds. A K-invariant K = 32 leave-one-seed-out reference was primary; K-dependent cross-fitting and the same-fold maximum were sensitivity and descriptive opportunity quantities. We additionally evaluated practical-equivalence grids, PR-AUC and training-defined minority-recall-constrained selection, constructed duplicate/weak/complementary controls, empirical correlated heteroskedastic recovery simulations, registry composition, compute and chemical support.")
    replace_paragraph(
        doc,
        "Results:",
        f"Results: Against the K-invariant full-registry reference, K = 32 minus K = 4 gap contrasts were negative in {values['negative']} of nine endpoints, indicating a smaller full-registry completion gap at K = 32; descriptive split-seed sensitivity intervals excluded zero for {values['exclude']}. At K = 32, {values['epsilon_success']:.1%} of selections were ε-successes at the retrospectively locked middle reporting tolerance. PR-AUC and minority-constrained selectors changed the ROC-AUC-selected candidate in {pr['candidate_changed_vs_roc']:.1%} and {minority['candidate_changed_vs_roc']:.1%} of classification audit units, respectively; the constrained selector changed outer minority recall by {minority_delta['outer_minority_recall']:+.4f} on average and did not reliably satisfy the 0.80 target on held-out folds.",
    )
    replace_paragraph(doc, "Conclusions:", "Conclusions: Candidate-pool expansion changed available opportunity and the stability with which finite validation realised it. The result depended on endpoint, registry composition, selection metric, candidate dependence, chemical support and split mechanism. K-invariant cross-fitting, practical-equivalence reporting and metric-matched selection reduced interpretive ambiguity but did not provide external validation or establish a universal effect of larger registries.")
    replace_paragraph(doc, "Scientific Contribution:", "Scientific Contribution: This study separates a K-invariant cross-fitted reference from K-dependent and same-fold opportunity quantities, and quantifies practical equivalence and metric-dependent selection in molecular benchmarks. Constructed dependence controls and empirical correlated heteroskedastic simulations show why nominal candidate count cannot substitute for effective search diversity. The resulting audit and reporting package is designed for third-party reproduction rather than architecture ranking.")
    replace_paragraph(doc, "Keywords:", "Keywords: molecular property prediction; candidate-pool expansion; nested cross-validation; cross-fitted reference; practical equivalence; PR-AUC; selection stability; chemical support")
    replace_paragraph(doc, "We therefore conducted", "We therefore conducted a retrospectively specified and subsequently locked, task-stratified audit rather than a model leaderboard. The central question was whether opportunities created by candidate-pool expansion could be realised reproducibly from finite validation information. Ten current seeded scaffold partitions were generated with the locked current split implementation for the 32-candidate registry. Historical unseeded GroupKFold outputs were retained only for data provenance and the split-transition audit. The six-endpoint registry-composition intervention and other analyses without complete ten-seed outputs were designated five-seed secondary analyses. The primary estimand used a K-invariant K = 32 leave-one-seed-out reference; K-dependent cross-fitting and the same-fold maximum were sensitivity and descriptive opportunity quantities.")
    replace_paragraph(doc, "For endpoint-specific K = 32", "For endpoint-specific K = 32 minus K = 4 contrasts in the lightweight registry, fold differences were averaged within each of ten split seeds and seed blocks were resampled 10,000 times. Classification used seeded stratified scaffold-group folds; regression used seeded scaffold-group-balanced folds for all ten current runs. The legacy unseeded regression GroupKFold outputs were retained only for a split-transition audit and were not mixed into the primary estimand. Resamples reduce Monte Carlo error but do not increase the ten-seed information base; the reported 95% intervals are descriptive split-seed sensitivity intervals, not population confidence intervals for unseen molecular endpoints. Classification ROC-AUC and regression RMSE effects were not pooled, and no endpoint-aggregation P value or confirmatory multiplicity family was defined.")
    replace_paragraph(doc, "The evaluation procedure for each candidate", "The evaluation procedure for each candidate was held constant across K. The unique current primary ten-seed matrix comprised 34,560 candidate fits: 17,280 from the first five current seed labels and 17,280 from seeds 83, 97, 113, 127 and 149. The corresponding recorded current-run candidate-fit time was 8,130.16 seconds. The historical five-seed outputs comprised 17,280 fits and 4,437.95 seconds, but they were a provenance source rather than an additional current-analysis component and were never added to the 34,560 total. The six-endpoint secondary composition intervention retained 64,616.35 downstream fit/predict seconds; its total fit count was not reconstructed.")
    replace_paragraph(doc, "Exposure units are analysis-specific", "Exposure units are analysis-specific and are not directly comparable across audit components. Current primary candidate-fit time covers the complete ten-seed lightweight registry; downstream composition time excludes model acquisition, encoder pretraining and cached embedding extraction. Historical timings remain in the provenance table and are not combined with current totals.")
    replace_paragraph(doc, "Five seeded scaffold partitions", "Ten current seeded scaffold partitions were generated independently for every classification and regression endpoint using seeds 11, 23, 37, 53, 71, 83, 97, 113, 127 and 149. Each partition contained three outer scaffold folds and three inner scaffold folds within every outer-training partition. Bemis–Murcko scaffold groups were kept intact; group allocation used seed-dependent random tie-breaking while balancing sample counts, and no model performance informed allocation. The split manifest records sample and scaffold counts, target summaries, split hashes and the absence of cross-fold scaffold overlap.")
    replace_paragraph(doc, "Because outer folds have overlapping", "Because outer folds have overlapping training sets, they are paired audit units rather than independent biological replications. For every primary endpoint, fold effects were first averaged within each of ten distinct split seeds before split-seed resampling. The three folds within a seed do not constitute three independent replications. Analyses with only seeds 11, 23, 37, 53 and 71 are explicitly labelled five-seed secondary analyses.")
    replace_paragraph(doc, "All unit-level metrics were averaged", "For the primary lightweight-registry estimands, unit-level metrics were averaged over three outer folds within each split seed and then summarized over ten seed blocks within endpoint. Five-seed secondary panels retained their original seed blocks and are labelled as such. Endpoint-level medians, interquartile ranges and ranges were used for cross-endpoint descriptive summaries; classification and regression were not pooled because ROC-AUC differences and RMSE increases are not exchangeable units.")
    replace_paragraph(doc, "For each endpoint and K, we formed a 15", "For the ten-seed primary audit, each endpoint and K produced a 30 × K outer-utility matrix and a 90 × K inner-utility matrix. Four transformations were analysed where ten-seed utilities were available: raw utilities; row-centred utilities; fixed-reference-relative utilities; and within-unit ranks. Any retained five-seed diversity panel uses a 15 × K outer matrix and is explicitly identified as secondary rather than silently combined with the primary audit.")
    replace_paragraph(doc, "Effective diversity was derived", "Effective diversity was derived from candidate-utility matrices rather than candidate labels or model-family counts. The current primary outer matrix contained 30 rows, indexed by ten seeds and three outer folds, while the corresponding inner matrix contained 90 rows. The outer-utility matrix characterized behavioural similarity on held-out scaffold groups; inner-utility estimates assessed whether redundancy was already visible during selection. Five-seed composition and multiview matrices remained separate secondary analysis units.")
    replace_paragraph(doc, "With n rows", "With n rows, a centred empirical K × K correlation matrix has rank at most n − 1 and can be unstable even when K < n. We therefore report both the empirical spectrum and Ledoit–Wolf shrinkage after column standardization. The shrinkage covariance was converted to a correlation matrix before eigenanalysis; this stabilizes the spectrum but does not create independent audit information.")
    replace_paragraph(doc, "Figure 1.", "Figure 1. Nested audit and evidence hierarchy. Three inner folds rank registered candidates and three outer folds audit frozen decisions. The lightweight registry uses ten seeded scaffold partitions; secondary composition and reliability panels retain their original prespecified units. K-invariant K = 32 and K-dependent cross-fitted references are separated from the descriptive same-fold opportunity bound, practical-equivalence sets, metric-matched selection, constructed candidate controls, recovery simulation, chemical-support analyses and bounded downstream compute.")
    replace_picture_before_caption(doc, "Figure 1.", FIGURES / "Figure_1_updated_audit_design.png")
    replace_picture_before_caption(doc, "Figure 3.", FIGURES / "Figure_3_primary_estimand_aligned.png")
    replace_paragraph(doc, "Figure 3.", "Figure 3. Chance-adjusted ranking calibration and K-invariant full-registry effects. (A) Five-seed secondary endpoint-median CAHit@3 and normalized MRR gain with endpoint IQRs and the 95% random-rank envelope. (B) Five-seed secondary positive-control recovery across six injected validation–audit signal levels and four candidate counts. (C) Ten-seed primary endpoint-specific K = 32 minus K = 4 full-registry completion-gap contrasts against the K-invariant K = 32 cross-fitted reference. Classification ROC-AUC and regression RMSE use separate axes; negative values indicate a smaller completion gap at K = 32, and filled markers denote split-seed sensitivity intervals that exclude zero. Panel C uses the same estimates and limits as Table 4. (D) Five-seed secondary registered-prefix, random-order, random-subset and family-balanced composition controls; all modes equal the complete registry at K = 32 by design.")

    replace_paragraph(doc, "2.8 Primary leave-one-seed-out", "2.8 Leave-one-seed-out references and opportunity-gap decomposition")
    replace_paragraph(doc, "The primary retrospective estimand used", "For each held-out seed s, the K-invariant full-registry reference j_ref,32,−s was the highest-mean-utility candidate across the other nine seeds in the complete 32-candidate registry. The K-dependent reference j_ref,K,−s was selected analogously within the eligible prefix C_K, and the same-fold finite-set best was the maximum-utility eligible candidate in the evaluated outer fold. We defined G_inv as K-invariant reference utility minus selected utility, G_dep as K-dependent reference utility minus selected utility, and G_same as the same-fold maximum minus selected utility. The availability component G_avail was the K-invariant reference utility minus the K-dependent reference utility, giving G_inv = G_avail + G_dep. Because j_ref,32,−s need not be eligible when K < 32, G_inv is a full-registry completion gap rather than pure eligible-set model-selection regret.")
    replace_paragraph(doc, "This cross-fitted reference reduces", "Reference selection was isolated from the held-out seed but reused the same endpoint population and split generator. It therefore reduces same-unit circularity without creating external validation. The ten primary seed blocks are sensitivity replicates rather than independent studies; five-seed secondary analyses were not substituted into these reference calculations.")
    replace_paragraph(doc, "Let u = (s, f)", "Let u = (s, f) index an outer audit unit, V(u,j) the mean inner-validation utility and A(u,j) the outer-audit utility. For the primary audit S_main = 10 and F = 3; for explicitly labelled secondary analyses S_secondary = 5. The eligible prefix C_K, candidate order and tie rules were fixed before the reported contrasts were calculated. The notation table and equations define the validation-selected candidate, K-invariant and K-dependent cross-fitted references, same-fold finite-set best, G_inv, G_dep, G_same, G_avail, CAHit@3, normalized MRR, entropy effective rank and normalized selection entropy.")
    replace_paragraph(doc, "contains all outer units", "The reference-training set contains all outer units from seeds other than held-out seed s. Thus the primary K-invariant and K-dependent references use the other nine of S_main = 10 seeds, whereas five-seed secondary analyses use the other four of S_secondary = 5. Equations (5)–(6) define the cross-fitted identities and gaps; the availability decomposition is stated explicitly in Section 2.8.")
    replace_paragraph(doc, "X is the outer-utility matrix", "X is the outer-utility matrix; S_cov in the Ledoit–Wolf expression denotes sample covariance and must not be confused with S_main = 10 or S_secondary = 5. T is the scaled-identity target, λ_i are the non-negative eigenvalues of the shrinkage correlation matrix and p_i their unit-sum proportions. Equations (7)–(10) define the transformations and effective ranks.")

    ai = find_paragraph(doc, "2.17 Use of generative")
    ai.text = "2.21 Use of generative artificial intelligence"
    additions = [
        ("2.17 K-invariant K = 32 cross-fitted reference", "For each endpoint and held-out seed, the reference candidate was selected once from all 32 candidates by mean outer utility across the other nine seeds, with registry order resolving ties. That identity was evaluated on each fold of the held-out seed and was held fixed for K = 4, 8, 16 and 32, even when it was not eligible for selection at smaller K. Regret was reference utility minus selected utility, equivalent to selected minus reference RMSE for regression; therefore a negative K = 32 minus K = 4 regret contrast favors K = 32. The estimand is K-invariant and seed-isolated, but it reuses the same public endpoint and split generator and is not an independent cohort."),
        ("2.18 Practical equivalence and near-equivalent sets", "Retrospectively locked sensitivity grids were 0.005, 0.010 and 0.020 ROC-AUC for classification and 0.025, 0.050 and 0.100 RMSE for regression. The middle values were working thresholds, not clinical or pharmacological minimum important differences. We reported ε-regret, ε-success, validation- and cross-fitted near-equivalent set sizes, set Jaccard overlap and whether the selected candidate belonged to the cross-fitted set."),
        ("2.19 PR-AUC and minority-recall-constrained selection", "The five classification endpoints were refitted on the frozen ten-seed nested splits to record inner ROC-AUC, PR-AUC and operating-point metrics. The minority label was the less frequent class in each training fold. Within each inner validation fold, a threshold was chosen to achieve minority recall of at least 0.80 while maximizing majority recall; candidate-specific thresholds were aggregated by the median across inner folds, without additional post-hoc probability calibration. The constrained selector maximized mean inner majority recall among candidates meeting the mean inner minority-recall target, then used minority recall, PR-AUC and registry order for ties. If no candidate met the constraint, the full eligible pool was retained and the same lexicographic rule was applied. Thresholds and candidate decisions were frozen before one-time outer-fold evaluation. We report candidate eligibility, inner feasibility, outer constraint satisfaction, minority and majority recall, false-negative rate, PR-AUC and ROC-AUC."),
        ("2.20 Constructed controls, order sensitivity and recovery simulation", "Exact duplicates copied registered utility vectors; near-duplicates combined 95% of an anchor with 5% of a donor utility vector. Weak and complementary-strong additions were chosen using only non-held-seed mean utility and utility-pattern correlation. Registry, cross-fitted best-first, worst-first, cost-first and 100 deterministic random orders were evaluated. Recovery simulations treated outer candidate utilities as fixed truth and added either an empirical candidate-correlated heteroskedastic residual process or an independent homoskedastic comparator at 0.5, 1 and 2 times the estimated noise scale, with 2,000 replicates per endpoint, K and scenario."),
    ]
    for heading, body in additions:
        add_before(ai, heading, "Heading 2")
        add_before(ai, body, "Normal")

    replace_paragraph(doc, "3.4 Cross-fitted", "3.4 K-invariant cross-fitted effects remained heterogeneous")
    replace_paragraph(doc, "At K = 32, the endpoint medians", "In the five-seed secondary effective-diversity reconstruction, the K = 32 endpoint medians of Ledoit–Wolf entropy rank were 2.98 for raw utilities, 24.23 after row centring, 5.86 for fixed-reference-relative utilities and 27.14 for within-unit ranks. These matrices capture common audit-unit difficulty, removal of common level shifts, prespecified-reference contrasts and ordering without utility spacing, respectively. They were not silently treated as ten-seed primary estimates (Figure 2; Tables S6–S7).")
    replace_paragraph(doc, "Estimator, seed, fold", "Estimator, seed, fold and reference sensitivities changed magnitudes but preserved the gap between nominal K and effective rank in this five-seed secondary analysis. Full IQRs, ranges, participation-ratio ranks and correlation summaries remain in Table S6; the ten-seed primary reference-gap results are reported separately in Sections 3.4 and 3.11.")
    replace_paragraph(doc, "Cross-fitted K = 32", f"Against the K-invariant K = 32 leave-one-seed-out reference, K = 32 minus K = 4 full-registry completion-gap contrasts were negative in {values['negative']} endpoints, indicating a smaller gap at K = 32, and positive in {values['positive']}. Descriptive split-seed sensitivity intervals excluded zero for {values['exclude']} endpoints. Figure 3C and Table 4 use the same endpoint estimates, interval limits and signs without pooling classification and regression scales.")
    replace_paragraph(doc, "The leave-one-seed reference attenuates", "The K-invariant reference prevents the comparator identity from changing with K and separates its selection from the held-out seed. It remains conditional on the same public endpoint population and split generator, so it is a retrospective sensitivity reference rather than external validation or deployable truth.")
    replace_paragraph(doc, "Table 4.", "Table 4. K-invariant cross-fitted candidate-pool effects.")
    table = doc.tables[3]
    fixed = values["fixed"]
    lookup = fixed.set_index("dataset")
    label_to_dataset = {
        "bace": "bace",
        "bbbp": "bbbp",
        "clintox": "clintox",
        "hia": "tdc_hia_hou",
        "p-gp": "tdc_pgp_broccatelli",
        "esol": "esol",
        "freesolv": "freesolv",
        "lipophilicity": "lipo",
        "caco-2": "tdc_caco2_wang",
    }
    for row in table.rows:
        name = row.cells[0].text.strip().lower()
        match = label_to_dataset.get(name)
        if match:
            item = lookup.loc[match]
            row.cells[1].text = format_effect(item["mean_natural_scale_effect"], item["seed_block_interval_low"], item["seed_block_interval_high"])
            if item["seed_block_interval_low"] > 0:
                direction = "Favors K = 4; interval excludes 0"
            elif item["seed_block_interval_high"] < 0:
                direction = "Favors K = 32; interval excludes 0"
            else:
                direction = "Uncertain"
            row.cells[2].text = direction
    component_table = doc.tables[1]
    for row in component_table.rows:
        if row.cells[0].text.strip() == "Controlled prefix audit":
            row.cells[2].text = "9 endpoints; K = 4, 8, 16 and 32; 10 seeds; 3 outer × 3 inner"
            row.cells[3].text = f"{values['primary_fits']:,} current primary candidate fits; {values['fit_seconds']:,.2f} recorded candidate-fit seconds; complete ten-seed coverage"

    discussion = find_paragraph(doc, "4 Discussion")
    results_target = discussion
    grid32 = values["epsilon_grid32"]
    class_grid = grid32.loc["classification"]
    reg_grid = grid32.loc["regression"]
    result_blocks = [
        ("3.11 Practical equivalence and metric-dependent selection", f"Holding the K = 32 cross-fitted reference identity fixed across K removed comparator drift. At K = 32, classification ε-success was {class_grid.loc[0.005, 'crossfit_epsilon_success']:.1%}, {class_grid.loc[0.010, 'crossfit_epsilon_success']:.1%} and {class_grid.loc[0.020, 'crossfit_epsilon_success']:.1%} across the 0.005/0.010/0.020 ROC-AUC grid; regression ε-success was {reg_grid.loc[0.025, 'crossfit_epsilon_success']:.1%}, {reg_grid.loc[0.050, 'crossfit_epsilon_success']:.1%} and {reg_grid.loc[0.100, 'crossfit_epsilon_success']:.1%} across the 0.025/0.050/0.100 RMSE grid. The pooled task-appropriate working-middle-threshold success rate was {values['epsilon_success']:.1%}; the mean cross-fitted set size was {values['epsilon_set']:.2f}, the selected-in-set rate was {values['epsilon_selected_in_set']:.1%} and mean validation–cross-fit set Jaccard overlap was {values['epsilon_jaccard']:.3f}. These are retrospectively locked reporting tolerances, not clinical or pharmacological thresholds. At K = 32, PR-AUC selection changed the ROC-AUC-selected candidate in {pr['candidate_changed_vs_roc']:.1%} of units and changed outer PR-AUC, ROC-AUC, minority recall, majority recall and false-negative rate by {pr_delta['outer_pr_auc']:+.4f}, {pr_delta['outer_roc_auc']:+.4f}, {pr_delta['outer_minority_recall']:+.4f}, {pr_delta['outer_majority_recall']:+.4f} and {pr_delta['outer_minority_miss_rate']:+.4f}, respectively. The minority-constrained selector changed candidates in {minority['candidate_changed_vs_roc']:.1%} of units and changed the same outer outcomes by {minority_delta['outer_pr_auc']:+.4f}, {minority_delta['outer_roc_auc']:+.4f}, {minority_delta['outer_minority_recall']:+.4f}, {minority_delta['outer_majority_recall']:+.4f} and {minority_delta['outer_minority_miss_rate']:+.4f}. At K = 32 an inner-feasible candidate existed in {values['minority_inner_eligibility']:.1%} of units, but the frozen decision achieved outer minority recall ≥0.80 in only {values['minority_outer_satisfaction']:.1%}; the negative mean recall change was retained rather than interpreted as automatic constraint transfer."),
        ("3.12 Constructed dependence controls and empirical recovery", f"Exact duplication increased nominal K without adding unique utility information, whereas near-duplicate, weak-first and complementary-first constructions changed effective rank and opportunity differently (Figure S25; Table S41). Under the empirical correlated heteroskedastic simulation at K = 32 and the estimated noise scale, mean top-1 recovery across endpoints was {rec['top1_recovery_mean'].mean():.3f}; observed mean same-fold gaps fell within the simulation's 95% envelope for {int(rec['observed_within_simulated_95pct_envelope'].sum())} of {len(rec)} endpoints (Figure S23; Table S42). These constructed and simulated analyses calibrate mechanisms and are neither empirical bias corrections nor independent validation."),
        ("3.13 Secondary contextual and negative analyses", "The five-seed secondary supplement also retained results that bound, rather than confirm, the ten-seed primary estimand. Twenty-two TDC endpoint summaries used heterogeneous historical budgets and were treated as contextual reliability evidence; AutoGluon results at 30, 300 and 1,800 seconds had unequal feature-preparation and hardware exposure; selection-risk correlations and nine leave-one-endpoint-out policies could not identify a transferable meta-selector. Conformal and CQR analyses improved conditional coverage in some cells while enlarging prediction sets, and MoleculeACE activity-cliff, beyond-rule-of-five, deduplication and failure-case panels exposed chemical-support and minority-safety limitations. These supplementary analyses are described in Sections S8–S13 and Tables S13–S20; none was pooled with the 34,560-fit ten-seed primary matrix."),
    ]
    for heading, body in result_blocks:
        add_before(results_target, heading, "Heading 2")
        add_before(results_target, body, "Normal")
        if heading.startswith("3.11"):
            add_picture_before(results_target, FIGURES / "Figure_8_consolidated_practical_equivalence_metric_selection.png")
            add_before(results_target, "Figure 8. Practical equivalence and metric-dependent selection in the ten-seed primary audit. (A) Classification ROC-AUC and regression RMSE gaps are shown on separate stacked axes sharing candidate count K; solid, dashed and dotted lines denote the K-invariant, K-dependent and same-fold estimands, respectively. (B) Cross-fitted ε-success is shown across K at the retrospectively locked middle reporting tolerances. (C) Mean cross-fitted near-equivalent set size is shown on one axis. (D) Endpoint-level PR-AUC and minority-recall-rule switching and outer trade-offs are shown for the five classification endpoints; the negative minority-recall results are retained. Panels A–D are arranged in a 2 × 2 layout.", "Caption")

    limit = find_paragraph(doc, "4.9 Limitations")
    limit.text = "4.11 Limitations"
    add_before(limit, "4.9 Practical equivalence and metric-matched selection", "Heading 2")
    add_before(limit, "Near-equivalent sets prevent negligible candidate differences from being interpreted as severe selection failures. However, the working ε values were retrospectively locked reporting tolerances rather than endpoint-specific clinical or pharmacological thresholds. PR-AUC and minority-recall-constrained selection exposed genuine candidate-switching and safety-performance trade-offs, but the 0.80 target is a study rule and must be redefined for deployment costs.", "Normal")
    add_before(limit, "4.10 Candidate dependence and finite validation", "Heading 2")
    add_before(limit, "Exact and near-duplicate controls show that nominal K can grow while effective utility information changes little. Weak and complementary orderings show that composition and exposure order can alter both available opportunity and selector burden. The empirical residual simulation recovered observed gaps for some but not all endpoints, supporting finite-validation noise as one mechanism without reducing endpoint heterogeneity to a single mechanical explanation.", "Normal")
    replace_paragraph(doc, "The nine-endpoint primary audit", "The nine-endpoint audit remains a retrospective evaluation of public datasets and does not provide prospective or independent external validation. Ten split seeds improve sensitivity resolution but are generated from one split mechanism and do not constitute ten independent studies. The K-invariant reference is isolated by seed, not by cohort or source.")
    replace_paragraph(doc, "Modern candidates were limited", "Modern candidates were limited to frozen representation probes and a separately locked one-epoch D-MPNN. Exact molecule-level pretraining manifests were unavailable for ChemBERTa and MoLFormer, so overlap with public benchmark molecules cannot be excluded. Equal-budget results depend on evaluated hardware and exclude encoder acquisition, pretraining and cached embedding extraction. Tanimoto-component transport covered three endpoints and one similarity rule; timestamps or independent source cohorts were unavailable for a valid temporal/source split.")
    replace_paragraph(doc, "Endpoint–pool–K and subset", "Endpoint–pool–K and subset cells reuse endpoints and folds and are not independent. The practical-equivalence thresholds and minority-recall target are retrospective study rules, not externally validated decision thresholds. Constructed utility-pattern controls are causal with respect to the constructed score matrices but do not reproduce every molecule-level error mechanism of a newly trained architecture.")
    replace_paragraph(doc, "The current evidence base does not include", "Full model pretraining corpora, independent prospective cohorts and source/time metadata were unavailable. Consequently, the study does not establish absence of pretrained-data overlap, temporal robustness or deployment utility. Complete probability-level reruns were retained locally and must be deposited with the final repository release before submission [AUTHOR MUST PROVIDE PERSISTENT REPOSITORY DOI/URL].")
    replace_paragraph(doc, "Within the evaluated endpoints", "Within the evaluated endpoints, candidate registries and split mechanisms, candidate-pool expansion altered model opportunity, validation–audit ranking agreement, practical equivalence, metric-dependent selection and bounded downstream cost. These changes depended on registry composition, candidate dependence, chemical support and endpoint. Nominal K and utility-pattern diversity described different search exposures; neither alone determined the K-invariant cross-fitted gap.")
    replace_paragraph(doc, "Molecular property-prediction benchmarks", "Molecular property-prediction benchmarks should report locked candidate eligibility, K-invariant and K-dependent cross-fitted references, the descriptive same-fold opportunity bound, near-equivalent sets, task-matched selection metrics, constructed dependence controls, selection stability, computational exposure and chemical-support boundaries. The present audit does not support universal claims that more candidates are necessarily worse or that any architecture class is generally superior.")
    replace_paragraph(doc, "Additional file 1", "Additional file 1 (PDF; .pdf). Title: Supplementary Methods and Results. Description: Supplementary evidence hierarchy, original analyses and completion methods/results for K-invariant references, practical equivalence, metric-matched selection, constructed controls, order sensitivity, recovery simulation and execution audit; Tables S1–S46 and Figures S1–S25 are cross-referenced.")
    replace_paragraph(doc, "Additional file 2", "Additional file 2 (XLSX; .xlsx). Title: Machine-readable Supplementary Tables S1–S46. Description: Original machine-readable tables plus fixed-reference units, ε sets, classification metric selection, constructed candidate controls, recovery simulation, order sensitivity, fit audit, pretraining-overlap status and the legacy-to-current rerun/split-transition audit.")
    replace_paragraph(doc, "Additional file 3", "Additional file 3 (PDF; .pdf). Title: Supplementary Figures S1–S25. Description: Original supplementary figures plus fixed-reference/equivalence, recovery, metric-selection and constructed-dependence figures.")
    replace_paragraph(doc, "Additional file 4", "Additional file 4 (ZIP; .zip). Title: Code and reproducibility package. Description: Source code, locked configurations, compact source results, manifests, integrity hashes and rerun entry points. Full probability-level outputs must also be deposited in the persistent repository named in Availability of data and materials.")
    replace_paragraph(doc, "BACE, beta-secretase", "BACE, beta-secretase 1; BBBP, blood–brain barrier penetration; CAHit@3, chance-adjusted Top-3 hit; CQR, conformalized quantile regression; D-MPNN, directed message-passing neural network; ECE, expected calibration error; HIA, human intestinal absorption; MACCS, Molecular ACCess System; MRR, mean reciprocal rank; NDCG, normalized discounted cumulative gain; P-gp, P-glycoprotein; PR-AUC, precision–recall area under the curve; RMSE, root mean squared error; ROC-AUC, receiver operating characteristic area under the curve.")
    replace_paragraph(doc, "Dataset-specific source locators", "The datasets supporting this article are public and the processed audit tables are included in Additional files 1–4. The complete code, frozen configurations, split manifests and probability-level outputs will be available in [AUTHOR MUST PROVIDE REPOSITORY NAME, PERSISTENT DOI AND HTTPS URL BEFORE SUBMISSION]. Journal of Cheminformatics requires third-party reproduction without registration; this placeholder is a submission blocker.")
    replace_paragraph(doc, "Software record.", "Software record. Project name: FZYC-Mol candidate-pool audit. Project home page and archived version: [AUTHOR MUST PROVIDE PUBLIC REPOSITORY HTTPS URL AND PERSISTENT ARCHIVE DOI]. Operating system: platform independent where the locked Python environment is supported. Programming language: Python 3.13.7. Licence: [AUTHOR MUST CONFIRM OSI-APPROVED LICENCE]. Restrictions on reuse: [AUTHOR MUST CONFIRM].")
    ai_heading = find_paragraph(doc, "2.21 Use of generative")
    ai_index = next(i for i, paragraph in enumerate(doc.paragraphs) if paragraph._p is ai_heading._p)
    ai_body = doc.paragraphs[ai_index + 1]
    declaration_target = find_paragraph(doc, "Competing interests")
    add_before(declaration_target, "Use of generative artificial intelligence", "Heading 2")
    add_before(declaration_target, ai_body.text, "Normal")
    ai_heading._element.getparent().remove(ai_heading._element)
    ai_body._element.getparent().remove(ai_body._element)
    set_journal_layout(doc)
    path = AUTHOR_REVIEW / "Main_manuscript_Journal_of_Cheminformatics_CLEAN_PENDING_AUTHOR_METADATA_AND_REPOSITORY.docx"
    doc.save(path)
    return path


def extract_base_supplement() -> tuple[Path, Path, Path, Path]:
    base = OUT / "base_supplement"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    with zipfile.ZipFile(BASE_SUPP_ZIP) as archive:
        archive.extractall(base)
    supp_docx = next(base.rglob("Additional_file_1_*EDITABLE.docx"))
    workbook = next(base.rglob("Additional_file_2_*.xlsx"))
    figures = next(base.rglob("Additional_file_3_*.pdf"))
    code = next(base.rglob("Additional_file_4_*.zip"))
    return supp_docx, workbook, figures, code


def add_df_table(doc: Document, title: str, frame: pd.DataFrame, decimals: int = 4) -> None:
    doc.add_paragraph(title, style="Heading 2")
    table = doc.add_table(rows=1, cols=len(frame.columns))
    table.style = "Table Grid"
    for cell, column in zip(table.rows[0].cells, frame.columns, strict=True):
        cell.text = str(column)
    for row in frame.itertuples(index=False):
        cells = table.add_row().cells
        for cell, value in zip(cells, row, strict=True):
            cell.text = f"{value:.{decimals}f}" if isinstance(value, (float, np.floating)) and np.isfinite(value) else str(value)


def build_supplement(base_docx: Path, values: dict[str, object]) -> Path:
    doc = Document(base_docx)
    replace_paragraph(doc, "Candidate-pool expansion", "Candidate-pool opportunity and selection stability under finite validation in molecular property prediction: a repeated nested audit")
    replace_paragraph(doc, "Evidence was retained in five levels", "Evidence was retained in five levels that answer different questions and are not combined into one leaderboard. The current primary analysis is the nine-endpoint, 32-candidate, ten-seed lightweight-registry audit reported in Section S22 and Tables S37–S46. The original effective-diversity, mechanism, multiview, registry-composition, reliability and chemical-support analyses in Sections S1–S16 retain five seeds where ten-seed outputs do not exist and are explicitly secondary. Historical TDC, AutoGluon, conformal, MoleculeACE, bRo5, deduplication and failure-case records remain contextual or negative evidence rather than independent confirmation.")
    replace_paragraph(doc, "Both classification and regression endpoints used five", "The current primary lightweight registry used ten distinct seed-specific scaffold partitions: 11, 23, 37, 53, 71, 83, 97, 113, 127 and 149. The original supplementary panels in Sections S3–S16 retain seeds 11, 23, 37, 53 and 71 unless a ten-seed source is explicitly cited. Regression Bemis–Murcko groups in the current primary matrix were allocated intact with seed-dependent tie breaking and sample-count balancing; legacy unseeded GroupKFold files are restricted to the split-transition provenance audit.")
    replace_paragraph(doc, "The unique machine-readable source contains 540", "The original chance-adjusted ranking source contains 540 endpoint–split-seed–outer-fold–K rows from nine endpoints, five split seeds, three outer folds and four K values and is therefore a five-seed secondary analysis. The ten-seed primary reference-gap and practical-equivalence units contain 1,080 rows and are reported separately in Tables S37–S38. No five-seed ranking estimate is presented as a ten-seed primary result.")
    replace_paragraph(doc, "For every endpoint, the three outer folds", "In the original five-seed secondary cross-fitted analysis, the three outer folds were averaged within each of five split seeds before resampling. The current primary K-invariant contrasts instead average folds within ten seed blocks and use the other nine seeds to select the held-out reference. Classification ROC-AUC and regression RMSE remain separate evidence strata in both analyses; their units are not pooled.")
    doc.add_heading("S22. Completion experiments for finite-validation realisation", level=1)
    doc.add_paragraph("These analyses complete the current primary lightweight-registry matrix. They were retrospectively specified and subsequently locked, not prospectively registered confirmation, and use the same public endpoint populations and split generator. The full seed set was 11, 23, 37, 53, 71, 83, 97, 113, 127 and 149; the primary outer and inner matrices therefore contain 30 × K and 90 × K rows, respectively.")
    doc.add_heading("S22.1 K-invariant reference and practical equivalence", level=2)
    doc.add_paragraph("For each held-out seed, one K = 32 candidate was selected from the other nine seeds and evaluated unchanged at every K. Practical-equivalence grids were 0.005/0.010/0.020 ROC-AUC and 0.025/0.050/0.100 RMSE. The middle thresholds are retrospective reporting tolerances, not endpoint-specific minimum important differences.")
    fixed = values["fixed"][["dataset", "task_type", "mean_natural_scale_effect", "seed_block_interval_low", "seed_block_interval_high"]]
    fixed = fixed.rename(columns={"dataset": "Endpoint", "task_type": "Type", "mean_natural_scale_effect": "Mean contrast", "seed_block_interval_low": "95% low", "seed_block_interval_high": "95% high"})
    add_df_table(doc, "Table S37. K-invariant K = 32 minus K = 4 effects", fixed)
    doc.add_heading("S22.2 Metric-matched classification selection", level=2)
    doc.add_paragraph("ROC-AUC, PR-AUC and minority-recall-constrained candidate selection were recalculated from inner-fold predictions on the frozen ten-seed splits. Minority status was defined from training labels. Thresholds targeted inner minority recall of at least 0.80 while maximizing majority recall and were aggregated by the inner-fold median. If no candidate met the constraint, the full eligible pool and the locked lexicographic tie rule were used. No additional post-hoc probability calibration was applied; all outcomes were evaluated once on the outer fold.")
    metric_rows = []
    for selector in ["pr_auc", "minority_constrained"]:
        base = values["metric32"].loc[selector]
        delta = values["metric_deltas"][selector]
        metric_rows.append({
            "Selector": selector,
            "Switch rate": base["candidate_changed_vs_roc"],
            "Delta ROC-AUC": delta["outer_roc_auc"],
            "Delta PR-AUC": delta["outer_pr_auc"],
            "Delta minority recall": delta["outer_minority_recall"],
            "Delta majority recall": delta["outer_majority_recall"],
            "Delta false-negative rate": delta["outer_minority_miss_rate"],
            "Inner feasible rate": values["minority_inner_eligibility"] if selector == "minority_constrained" else np.nan,
            "Outer target-satisfaction rate": values["minority_outer_satisfaction"] if selector == "minority_constrained" else np.nan,
        })
    metric = pd.DataFrame(metric_rows)
    add_df_table(doc, "Table S40. K = 32 selector comparison", metric)
    doc.add_heading("S22.3 Constructed candidate controls and order sensitivity", level=2)
    doc.add_paragraph("Exact duplicates and 95% anchor near-duplicates were constructed from stored score vectors. Weak and complementary-strong candidate orders were learned only from non-held seeds. Best-first, worst-first, cost-first and 100 random permutations assess order sensitivity without additional fitting.")
    controls = values["control_summary"]
    controls = controls[["control", "pool_size", "effective_rank", "same_fold_gap", "crossfit_gap", "available_opportunity"]].rename(columns={"control": "Control", "pool_size": "K", "effective_rank": "Effective rank", "same_fold_gap": "Same-fold gap", "crossfit_gap": "Cross-fit gap", "available_opportunity": "Available opportunity"})
    add_df_table(doc, "Table S41. Constructed control summary", controls)
    doc.add_heading("S22.4 Correlated heteroskedastic recovery simulation", level=2)
    doc.add_paragraph("Validation-minus-audit residual covariance was estimated separately by endpoint. Positive-semidefinite eigenvalue clipping was applied before simulation. Empirical correlated heteroskedastic and independent homoskedastic noise were compared at 0.5, 1 and 2 times the estimated scale, using 2,000 replicates per endpoint, K and scenario.")
    recovery = values["recovery32"][["dataset", "simulated_mean_gap", "simulated_gap_interval_low", "simulated_gap_interval_high", "top1_recovery_mean", "observed_within_simulated_95pct_envelope"]]
    recovery = recovery.rename(columns={"dataset": "Endpoint", "simulated_mean_gap": "Mean simulated gap", "simulated_gap_interval_low": "95% low", "simulated_gap_interval_high": "95% high", "top1_recovery_mean": "Top-1 recovery", "observed_within_simulated_95pct_envelope": "Observed covered"})
    add_df_table(doc, "Table S42. K = 32 empirical recovery summary", recovery)
    doc.add_heading("S22.5 Execution and unavailable audits", level=2)
    doc.add_paragraph(f"The unique current ten-seed lightweight registry comprised {values['primary_fits']:,} candidate fits and {values['fit_seconds']:,.2f} recorded candidate-fit seconds. The first-five-seed current subset contains 17,280 of these fits; it is not added again. Historical five-seed outputs comprised 17,280 fits and 4,437.95 seconds and remain provenance only. Legacy regression outputs used unseeded GroupKFold and were excluded from the current primary matrix. The maximum legacy-to-current classification difference was {values['classification_rerun_max_difference']:.6f}; the regression split-transition difference reached {values['regression_transition_max_difference']:.4f} and is an estimand change, not numerical reproducibility error. Timestamps, independent source-cohort identifiers and exact molecule-level pretraining manifests were unavailable; temporal/source validation was not performed and pretrained-data overlap cannot be excluded.")
    path = AUTHOR_REVIEW / "Additional_file_1_Supplementary_Methods_and_Results_EDITABLE_r2.docx"
    doc.save(path)
    return path


def write_sheet(wb, name: str, frame: pd.DataFrame) -> None:
    if name in wb.sheetnames:
        del wb[name]
    ws = wb.create_sheet(name)
    ws.append(list(frame.columns))
    for row in frame.itertuples(index=False, name=None):
        ws.append([None if (isinstance(v, float) and not np.isfinite(v)) else v for v in row])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    fill = PatternFill("solid", fgColor="D9EAF7")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for column in range(1, min(ws.max_column, 20) + 1):
        width = max(len(str(ws.cell(1, column).value)), 10)
        for row in range(2, min(ws.max_row, 200) + 1):
            value = ws.cell(row, column).value
            width = max(width, min(len(str(value)) if value is not None else 0, 45))
        ws.column_dimensions[get_column_letter(column)].width = min(width + 2, 48)


def build_workbook(base: Path) -> Path:
    wb = load_workbook(base)
    data = {
        "S37_FixedRef": pd.read_csv(TABLES / "fixed_reference_k32_vs_k4_contrasts.csv"),
        "S38_Epsilon": pd.read_csv(TABLES / "epsilon_near_equivalence_units.csv"),
        "S39_MetricSel": pd.read_csv(TABLES / "classification_metric_selection_units.csv"),
        "S40_MetricCmp": pd.read_csv(TABLES / "classification_metric_selector_comparisons.csv"),
        "S41_Controls": pd.read_csv(TABLES / "constructed_candidate_control_units.csv"),
        "S42_Recovery": pd.read_csv(TABLES / "empirical_heteroskedastic_recovery_simulation.csv"),
        "S43_Order": pd.read_csv(TABLES / "candidate_order_sensitivity_units.csv").groupby(["dataset", "order_rule", "pool_size"], as_index=False).agg(mean_crossfit_gap=("crossfit_gap", "mean"), mean_same_fold_gap=("same_fold_gap", "mean"), mean_fit_seconds=("mean_inner_fit_seconds_of_eligible", "mean")),
        "S44_FitAudit": pd.read_csv(TABLES / "fit_execution_audit.csv"),
        "S45_Pretrain": pd.read_csv(TABLES / "pretraining_overlap_audit.csv"),
        "S46_RerunQC": pd.read_csv(TABLES / "legacy_to_current_rerun_audit.csv"),
    }
    for name, frame in data.items():
        write_sheet(wb, name, frame)
    if "Paper43_Index" in wb.sheetnames:
        del wb["Paper43_Index"]
    index = wb.create_sheet("Paper43_Index", 0)
    index.append(["Table", "Worksheet", "Description", "Rows (formula)"])
    descriptions = [
        "K-invariant cross-fitted K=32 minus K=4 contrasts",
        "Practical-equivalence and near-equivalent set units",
        "ROC-AUC, PR-AUC and minority-constrained selections",
        "Alternative-selector comparisons with ROC-AUC",
        "Constructed duplicate, weak and complementary controls",
        "Empirical correlated heteroskedastic recovery simulation",
        "Candidate-order sensitivity summary",
        "Candidate-fit execution audit",
        "Pretraining-overlap audit status",
        "Classification rerun reproducibility against stored results",
    ]
    for i, ((name, frame), description) in enumerate(zip(data.items(), descriptions, strict=True), start=37):
        index.append([f"S{i}", name, description, f"=COUNTA('{name}'!A:A)-1"])
    index.freeze_panes = "A2"
    index.auto_filter.ref = index.dimensions
    for cell in index[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="BDD7EE")
    for column, width in {"A": 10, "B": 22, "C": 65, "D": 18}.items():
        index.column_dimensions[column].width = width
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    path = UPLOAD / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S46.xlsx"
    wb.save(path)
    return path


def figure_page(image: Path, output: Path, title: str, caption: str) -> None:
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Heading2"]), Spacer(1, 4 * mm)]
    img = Image.open(image)
    max_w, max_h = 175 * mm, 205 * mm
    scale = min(max_w / img.width, max_h / img.height)
    story.append(RLImage(str(image), width=img.width * scale, height=img.height * scale))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(caption, styles["BodyText"]))
    SimpleDocTemplate(str(output), pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm, topMargin=15 * mm, bottomMargin=15 * mm).build(story)


def build_supplementary_figures(base: Path) -> Path:
    specs = [
        ("S22", "Practical equivalence and metric-dependent selection", FIGURES / "Figure_8_consolidated_practical_equivalence_metric_selection.png", "Ten-seed primary results. K-invariant, K-dependent and same-fold gaps use separate classification and regression axes; ε-success and set size use separate panels without a dual axis; endpoint-level metric-switching and negative minority-recall effects are retained. Full sensitivity grids are in Tables S38–S40."),
        ("S23", "Empirical correlated heteroskedastic recovery", FIGURES / "Figure_3_empirical_recovery_simulation.png", "Top-1 recovery is shown under the endpoint-specific empirical residual covariance at the estimated noise scale. Simulations use 2,000 replicates per endpoint and K."),
        ("S24", "Metric-dependent classification selection", FIGURES / "Figure_5_metric_dependent_selection.png", "PR-AUC and training-defined minority-recall-constrained selection are compared with ROC-AUC selection across five classification endpoints, ten seeds and three outer folds."),
        ("S25", "Constructed candidate-dependence controls", FIGURES / "Figure_6_constructed_candidate_controls.png", "Exact duplicates, 95% anchor near-duplicates, weak additions, complementary-strong ordering and the registered pool distinguish nominal K from utility-pattern diversity."),
    ]
    pages = []
    for number, title, image, caption in specs:
        page = OUT / f"Supplementary_Figure_{number}.pdf"
        figure_page(image, page, f"Supplementary Figure {number}. {title}", caption)
        pages.append(page)
    writer = PdfWriter()
    for path in [base, *pages]:
        for page in PdfReader(str(path)).pages:
            writer.add_page(page)
    output = UPLOAD / "Additional_file_3_Supplementary_Figures_S1-S25.pdf"
    with output.open("wb") as handle:
        writer.write(handle)
    return output


def build_code_package(base: Path) -> Path:
    output = UPLOAD / "Additional_file_4_Code_and_reproducibility_package_r2.zip"
    shutil.copy2(base, output)
    scripts = [
        ROOT / "scripts" / "run_expanded_nested_candidate_pool_20260621.py",
        ROOT / "scripts" / "run_paper43_nested_completion_20260726.ps1",
        ROOT / "scripts" / "run_paper43_regression_split_completion_20260726.ps1",
        ROOT / "scripts" / "run_paper43_additional_lane1_20260726.ps1",
        ROOT / "scripts" / "run_paper43_additional_lane2_20260726.ps1",
        ROOT / "scripts" / "run_paper43_additional_lane3_resume97_20260726.ps1",
        ROOT / "scripts" / "analyze_paper43_completion_experiments_20260726.py",
        ROOT / "scripts" / "build_paper43_consolidated_figure8_20260726.py",
        ROOT / "scripts" / "build_paper43_primary_figure3_20260726.py",
        ROOT / "scripts" / "build_paper43_jcheminform_package_20260726.py",
    ]
    with zipfile.ZipFile(output, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in scripts:
            archive.write(path, f"paper43_completion/scripts/{path.name}")
        for path in sorted((OUT / "source_data").glob("*.csv")):
            archive.write(path, f"paper43_completion/source_data/{path.name}")
        run_roots = {
            "classification_metric_rerun": ROOT / "results" / "paper43_metric_rerun",
            "regression_split_manifest_rerun": ROOT / "results" / "paper43_regression_split_rerun",
            "additional_seeds": ROOT / "results" / "paper43_additional_seeds",
        }
        retained_names = {
            "complete.json",
            "candidate_registry.csv",
            "inner_scores.csv",
            "outer_candidate_scores.csv",
            "split_manifest.csv",
        }
        for source_name, run_root in run_roots.items():
            for path in sorted(p for p in run_root.rglob("*") if p.is_file() and p.name in retained_names):
                relative = path.relative_to(run_root).as_posix()
                archive.write(path, f"paper43_completion/run_records/{source_name}/{relative}")
        archive.write(OUT / "EXPERIMENT_COMPLETION_MANIFEST.json", "paper43_completion/EXPERIMENT_COMPLETION_MANIFEST.json")
        archive.writestr(
            "paper43_completion/REPOSITORY_DEPOSITION_REQUIRED.txt",
            "Before submission, deposit this package plus full probability-level outputs in a persistent public repository and replace the manuscript placeholder with repository name, DOI and HTTPS URL.\n",
        )
    return output


def build_repository_deposition_bundle(code_package: Path) -> Path:
    REPOSITORY.mkdir(parents=True, exist_ok=True)
    output = REPOSITORY / "FZYC_Mol_candidate_pool_audit_repository_deposition_bundle.zip"
    run_roots = {
        "primary_old_five_seeds": ROOT / "results" / "nested_selection" / "repeated_nested",
        "classification_metric_rerun": ROOT / "results" / "paper43_metric_rerun",
        "regression_split_manifest_rerun": ROOT / "results" / "paper43_regression_split_rerun",
        "additional_five_seeds": ROOT / "results" / "paper43_additional_seeds",
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        archive.write(code_package, f"submission/{code_package.name}")
        for path in sorted((ROOT / "scripts").glob("*paper43*")):
            if path.is_file():
                archive.write(path, f"scripts/{path.name}")
        archive.write(ROOT / "scripts" / "run_expanded_nested_candidate_pool_20260621.py", "scripts/run_expanded_nested_candidate_pool_20260621.py")
        for source_name, run_root in run_roots.items():
            for path in sorted(p for p in run_root.rglob("*") if p.is_file()):
                archive.write(path, f"results/{source_name}/{path.relative_to(run_root).as_posix()}")
        for folder_name in ["source_data", "figures", "additional_files"]:
            folder = OUT / folder_name
            for path in sorted(p for p in folder.rglob("*") if p.is_file()):
                archive.write(path, f"derived/{folder_name}/{path.relative_to(folder).as_posix()}")
        archive.write(OUT / "EXPERIMENT_COMPLETION_MANIFEST.json", "EXPERIMENT_COMPLETION_MANIFEST.json")
        archive.write(OUT / "Journal_of_Cheminformatics_requirements_snapshot_20260726.md", "Journal_of_Cheminformatics_requirements_snapshot_20260726.md")
        archive.writestr(
            "README_DEPOSITION.txt",
            "Deposit this complete bundle in a persistent public repository that permits anonymous access. Before manuscript submission, add an OSI-approved code licence, confirm dataset licences, obtain the repository DOI and HTTPS URL, and replace all manuscript placeholders. The bundle contains probability-level outputs and exact split manifests; it is not an upload-site Additional file because it may exceed the journal's 20 MB per-file limit.\n",
        )
    return output


def build_graphical_abstract() -> Path:
    fig = plt.figure(figsize=(9.2, 3.0), dpi=100, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    boxes = [
        (0.02, 0.24, 0.20, 0.52, "Locked registry\nK = 4, 8, 16, 32", "#DCEAF7"),
        (0.28, 0.24, 0.20, 0.52, "Finite validation\nmetric-matched\nselection", "#FFF2CC"),
        (0.54, 0.24, 0.20, 0.52, "Outer audit\nK-invariant reference", "#E2F0D9"),
        (0.80, 0.24, 0.18, 0.52, "Report opportunity,\nε-sets and stability", "#FCE4D6"),
    ]
    for x, y, w, h, text, color in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, edgecolor="#333333", linewidth=1.2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=10, weight="bold")
    for start, end in [(0.22, 0.28), (0.48, 0.54), (0.74, 0.80)]:
        ax.annotate("", xy=(end, 0.50), xytext=(start, 0.50), arrowprops=dict(arrowstyle="->", lw=1.8, color="#333333"))
    ax.text(0.5, 0.08, "Candidate expansion creates opportunity only when finite validation can realise it reproducibly", ha="center", fontsize=11)
    path = UPLOAD / "Graphical_Abstract_920x300.png"
    fig.savefig(path, dpi=100, facecolor="white")
    plt.close(fig)
    image = Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
    image = image.resize((920, 300), resample=Image.Resampling.LANCZOS)
    image.save(path, optimize=True)
    return path


def build_design_figure() -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=180)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")
    blocks = [
        (0.2, 4.8, 1.7, 1.2, "9 endpoints\n32 candidates", "#DCEAF7"),
        (2.3, 4.8, 1.8, 1.2, "10 split seeds\n3 × 3 nested folds", "#E2F0D9"),
        (4.5, 4.8, 2.1, 1.2, "K-invariant K = 32\ncross-fit", "#FFF2CC"),
        (7.0, 4.8, 2.5, 1.2, "Natural-scale effects\nseed-block intervals", "#FCE4D6"),
        (2.3, 2.6, 1.8, 1.2, "PR-AUC + minority\nconstraint (training only)", "#EDE7F6"),
        (4.5, 2.6, 2.1, 1.2, "ε-sets +\ndependence controls", "#EDE7F6"),
        (7.0, 2.6, 2.5, 1.2, "Correlated heteroskedastic\nrecovery simulation", "#EDE7F6"),
        (2.3, 0.5, 4.3, 1.0, "Secondary five-seed composition,\ncompute and stability", "#F2F2F2"),
        (7.0, 0.5, 2.5, 1.0, "Chemical support +\n3-endpoint transfer", "#F2F2F2"),
    ]
    for x, y, w, h, label, color in blocks:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, edgecolor="#333333", lw=1.0))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7.2)
    for a, b in [((1.9, 5.4), (2.3, 5.4)), ((4.1, 5.4), (4.5, 5.4)), ((6.6, 5.4), (7.0, 5.4)), ((3.2, 4.8), (3.2, 3.8)), ((5.55, 4.8), (5.55, 3.8)), ((8.25, 4.8), (8.25, 3.8)), ((4.1, 1.5), (4.1, 2.6)), ((8.25, 1.5), (8.25, 2.6))]:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=1.0, color="#444444"))
    ax.text(0.2, 6.5, "Primary question: can expanded opportunity be realised reproducibly from finite validation?", fontsize=10, weight="bold")
    path = FIGURES / "Figure_1_updated_audit_design.png"
    fig.savefig(path, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURES / "Figure_1_updated_audit_design.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def build_cover_letter() -> Path:
    doc = Document()
    doc.add_heading("Cover letter — Journal of Cheminformatics", level=1)
    doc.add_paragraph("[DATE REQUIRED]")
    doc.add_paragraph("Dear Editors-in-Chief,")
    doc.add_paragraph("We submit the Research article ‘Realising candidate-pool opportunities under finite validation in molecular property prediction: a repeated nested audit’ for consideration in Journal of Cheminformatics. The study addresses an auditable but under-reported component of molecular benchmarking: whether opportunities introduced by a larger candidate registry can be realised reproducibly from finite validation information.")
    doc.add_paragraph("The manuscript contributes a K-invariant cross-fitted reference, practical-equivalence sets, PR-AUC and minority-recall-constrained selection, constructed dependence controls and empirical correlated heteroskedastic recovery simulations across nine public endpoints. Its purpose is methodological audit and reporting guidance, not a leaderboard or a universal claim that larger registries are harmful.")
    doc.add_paragraph("All conclusions are supported by machine-readable additional files and a rerunnable code package. [AUTHOR MUST INSERT PUBLIC REPOSITORY DOI/URL AND CONFIRM THAT ACCESS REQUIRES NO REGISTRATION.] The manuscript is not under consideration elsewhere, all authors have approved submission, and competing interests are declared in the manuscript. [AUTHOR MUST CONFIRM THESE STATEMENTS.]")
    doc.add_paragraph("Sincerely,\n[CORRESPONDING AUTHOR NAME, DEGREE, AFFILIATION, EMAIL AND POSTAL ADDRESS REQUIRED]")
    path = AUTHOR_REVIEW / "Cover_letter_DRAFT_PENDING_AUTHOR_CONFIRMATION.docx"
    doc.save(path)
    return path


def write_submission_audit(paths: list[Path]) -> None:
    rows = [
        ["Research criteria", "Entirely reproducible by third parties", "PARTIAL", "Package prepared; persistent public DOI/URL and full probability outputs still require author deposition"],
        ["Abstract", "≤350 words and Scientific Contribution ≤3 sentences", "PASS", "Structured abstract updated"],
        ["Main text", "Double spacing, line and page numbering, no manual page breaks", "PASS", "Applied in DOCX; Word render audit pending"],
        ["Figures", "Editable/high-resolution; title ≤15 words; legend ≤300 words", "PASS", "PDF and 600-dpi PNG supplied"],
        ["Additional files", "Sequentially named, cited, machine-readable", "PASS", "Additional files 1–4 updated"],
        ["Declarations", "All required headings", "PARTIAL", "Author, funding, contribution, competing-interest and acknowledgement confirmation required"],
        ["Repository", "Availability section includes code links", "BLOCKED", "Persistent repository DOI/URL not available in workspace"],
        ["External validation", "Independent/time/source audit", "NOT FEASIBLE", "No timestamp/source cohort metadata; three-endpoint structure-separation audit retained"],
        ["Pretraining overlap", "Molecule-level corpus overlap", "UNRESOLVED", "Checkpoint-level models identified; exact molecule manifests unavailable"],
    ]
    pd.DataFrame(rows, columns=["Requirement", "Journal expectation", "Status", "Evidence or blocker"]).to_csv(OUT / "Journal_of_Cheminformatics_submission_audit.csv", index=False)
    checksums = []
    for path in paths:
        checksums.append([path.name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()])
    pd.DataFrame(checksums, columns=["file", "bytes", "sha256"]).to_csv(OUT / "SHA256SUMS.csv", index=False)


def main() -> None:
    for path in [UPLOAD, AUTHOR_REVIEW, REPOSITORY]:
        path.mkdir(parents=True, exist_ok=True)
    values = load_values()
    build_design_figure()
    supp_docx, workbook, supp_figures, code = extract_base_supplement()
    main_doc = build_main(values)
    supplementary_doc = build_supplement(supp_docx, values)
    workbook_path = build_workbook(workbook)
    figure_path = build_supplementary_figures(supp_figures)
    code_path = build_code_package(code)
    repository_bundle = build_repository_deposition_bundle(code_path)
    graphical = build_graphical_abstract()
    cover = build_cover_letter()
    write_submission_audit([main_doc, supplementary_doc, workbook_path, figure_path, code_path, graphical, cover])
    result = {
        "main_manuscript": str(main_doc),
        "supplementary_docx": str(supplementary_doc),
        "workbook": str(workbook_path),
        "supplementary_figures": str(figure_path),
        "code_package": str(code_path),
        "repository_deposition_bundle": str(repository_bundle),
        "graphical_abstract": str(graphical),
        "cover_letter": str(cover),
    }
    (OUT / "PACKAGE_BUILD.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
