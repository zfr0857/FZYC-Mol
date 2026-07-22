from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(r"C:\Users\Administrator\.codex\plugins\cache\antigravity-awesome-skills\agyb-aas-documents-presentations\12.6.0\skills\docx-official")
sys.path.insert(0, str(SKILL))
from scripts.document import Document, DocxXMLEditor  # noqa: E402
from update_paper26_split_regime_documents_20260716 import (  # noqa: E402
    EN_ABSTRACT_CONCLUSIONS,
    EN_ABSTRACT_METHODS,
    EN_ABSTRACT_RESULTS,
    EN_CONTRIBUTION,
)


UNPACKED = ROOT / "output" / "paper26_split_regime_transfer_revision_20260716" / "tracked_unpacked"


def paragraph_text(node) -> str:
    values = []
    for tag in ("w:t", "w:delText"):
        for item in node.getElementsByTagName(tag):
            values.append("".join(child.data for child in item.childNodes if child.nodeType == child.TEXT_NODE))
    return "".join(values)


def replace_paragraph(doc: Document, prefix: str, new_text: str) -> None:
    editor = doc["word/document.xml"]
    node = editor.get_node(tag="w:p", contains=prefix)
    old_text = paragraph_text(node)
    ppr_nodes = node.getElementsByTagName("w:pPr")
    ppr = ppr_nodes[0].toxml() if ppr_nodes else ""
    replacement = (
        f"<w:p>{ppr}"
        f"<w:del><w:r><w:delText>{escape(old_text)}</w:delText></w:r></w:del>"
        f"<w:ins><w:r><w:t>{escape(new_text)}</w:t></w:r></w:ins>"
        "</w:p>"
    )
    editor.replace_node(node, replacement)


def tracked_paragraph(text: str, style: str) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    raw = f"<w:p>{ppr}<w:r><w:t>{escape(text)}</w:t></w:r></w:p>"
    return DocxXMLEditor.suggest_paragraph(raw)


def insert_sequence(doc: Document, anchor_prefix: str, items: list[tuple[str, str]]) -> None:
    editor = doc["word/document.xml"]
    anchor = editor.get_node(tag="w:p", contains=anchor_prefix)
    current = anchor
    for text, style in items:
        nodes = editor.insert_after(current, tracked_paragraph(text, style))
        current = nodes[-1]


def main() -> None:
    doc = Document(str(UNPACKED), author="OpenAI Codex", initials="OC", track_revisions=True)
    replacements = {
        "Methods:": EN_ABSTRACT_METHODS,
        "Results:": EN_ABSTRACT_RESULTS,
        "Conclusions:": EN_ABSTRACT_CONCLUSIONS,
        "Scientific Contribution:": EN_CONTRIBUTION,
        "Under a retrospectively locked": (
            "Under a retrospectively locked repeated nested scaffold evaluation, how did candidate-pool expansion relate to matrix-dependent "
            "utility-pattern diversity, chance-adjusted ranking fidelity, cross-fitted selection gaps and representation-composition effects, "
            "and did the principal audit directions persist under a stricter structure-separated split? We address this limited question by "
            "separating nominal K from matrix-defined diversity, calibrating ranking measures against negative and positive controls, combining "
            "cross-fitted and matched-size analyses, and adding a three-endpoint split-regime transfer audit. Candidate eligibility, failed fits, "
            "split identities, source hashes and computational exposure remain part of the audit trail. The study evaluates model-selection "
            "behaviour and does not propose a new molecular predictor or an independent external validation."
        ),
        "2.13 Statistical inference": "2.14 Statistical inference",
        "4.7 Limitations": "4.8 Limitations",
        "The primary registry was intentionally": (
            "The primary registry was intentionally near-duplicate, only nine endpoints entered the main audit, and effective diversity at the "
            "largest registry was estimated from 15 outer rows. The split-regime transfer audit covered only ClinTox, BACE and ESOL, used one "
            "Morgan-derived 0.70 component threshold and did not include temporal or target-aware source-selection splits. Shrinkage, hierarchical "
            "resampling and split transfer expose sensitivity but cannot replace additional independent audit units. The study was retrospective "
            "and not prospectively preregistered, and public outer folds were not an independent lockbox."
        ),
        "Within the studied endpoints": (
            "Within the studied endpoints, candidate-pool expansion was accompanied by weaker chance-adjusted validation ranking and heterogeneous "
            "model-selection gaps. In three representative endpoints, the K = 32 minus K = 4 CAHit@3 change remained negative and the cross-fitted "
            "gap direction remained positive under a Tanimoto-component split, but effect magnitude and interval exclusion changed. Estimated "
            "candidate diversity remained strongly matrix dependent and only partly stable across split regimes."
        ),
        "Molecular model-selection studies should": (
            "Molecular model-selection studies should jointly report candidate eligibility, nominal K, matrix-dependent utility-pattern diversity, "
            "chance-adjusted ranking fidelity, endpoint-specific same-unit and cross-fitted gaps, split uniqueness and split-regime sensitivity, "
            "computational exposure, failed candidates and chemical-support boundaries. These quantities support transparent audit interpretation "
            "but do not define a universal selector or a deployment-ready screening system."
        ),
        "Additional file 1.": "Additional file 1. Supplementary Methods and Results, including the split-regime transfer audit.",
        "Additional file 2.": "Additional file 2. Machine-readable Supplementary Tables (Tables S1-S26; XLSX).",
        "Additional file 3.": "Additional file 3. Supplementary Figures (Figures S1-S18; PDF).",
        "Public dataset provenance": (
            "Public dataset provenance is listed in Additional file 2: Table S1. Derived fold-level tables, split manifests, source hashes, "
            "split-regime transfer outputs and analysis code are supplied in the accompanying submission package."
        ),
    }
    for prefix, text in replacements.items():
        replace_paragraph(doc, prefix, text)

    insert_sequence(doc, "These analyses were retained", [
        ("2.13 Split-regime transfer audit", "Heading2"),
        ("ClinTox, BACE and ESOL represented rare-class classification, regular classification and regression, respectively. The locked 32-candidate Morgan-512 registry, candidate order, K = 4, 8, 16 and 32 prefixes, seeds 11, 23, 37, 53 and 71, and three outer by three inner folds were retained. Scaffold results reused the locked source-of-record outputs. For the new structure-separated rerun, molecular pairs with Morgan-512 Tanimoto similarity at least 0.70 were connected, and each connected component was kept intact during outer and inner allocation. The threshold and allocation rule were fixed before formal model fitting after splitter feasibility checks; model performance did not inform grouping.", "Normal"),
        ("A seeded greedy allocator balanced sample counts and, for classification, both class counts across intact components. Every formal inner and outer split was required to retain both classes where applicable, keep components disjoint and have maximum cross-fold Tanimoto below 0.70; random fallback was prohibited. The transfer audit added 5,760 candidate fits. Direction transport was assessed for CAHit@3 change from K = 4 to K = 32, leave-one-seed-out cross-fitted K = 32 minus K = 4 selection gaps and Ledoit–Wolf effective ranks under the four prespecified matrix transformations. This was a robustness analysis on three selected endpoints, not a new confirmatory population sample.", "Normal"),
    ])
    insert_sequence(doc, "Figure 6.", [
        ("3.9 Audit directions transferred but effect magnitudes changed under structure separation", "Heading2"),
        ("The formal similarity-cluster rerun completed all 1,440 outer and 4,320 inner candidate-utility evaluations without random-split fallback. Each endpoint had 15 unique outer-fold assignments, all inner and outer component sets were disjoint, test-fold sizes ranged from 376 to 505 molecules, and the largest observed cross-fold Tanimoto was 0.699 (Additional file 2: Table S26).", "Normal"),
        ("CAHit@3 changes from K = 4 to K = 32 were negative under scaffold and similarity-cluster splits for BACE (-0.662 and -0.009), ClinTox (-0.956 and -0.690) and ESOL (-0.883 and -0.515). Thus the direction persisted in all three endpoints, but the BACE similarity-cluster change was close to zero and normalized MRR did not decline uniformly. The result supports transport of the prespecified CAHit@3 direction, not universal degradation of every ranking metric (Additional file 3: Figure S18A).", "Normal"),
        ("Cross-fitted K = 32 minus K = 4 gaps were positive in both regimes for all three endpoints. The scaffold and similarity-cluster effects were 0.0009 (-0.0046 to 0.0048) and 0.0178 (0.0124 to 0.0243) for BACE, 0.0098 (0.0049 to 0.0138) and 0.0049 (-0.0089 to 0.0215) for ClinTox, and 0.0573 (0.0411 to 0.0749) and 0.0017 (-0.0072 to 0.0107) for ESOL. Classification ROC-AUC loss and regression RMSE loss remained on separate scales. Effective-rank estimates across endpoint, K and transformation combinations had Spearman correlation 0.832 between regimes, while absolute values still changed materially (Figure S18B-D; Tables S24-S25).", "Normal"),
    ])
    insert_sequence(doc, "ClinTox illustrates why", [
        ("4.7 Split-regime transfer reduced, but did not remove, design dependence", "Heading2"),
        ("Preserving the CAHit@3 change direction and the cross-fitted gap direction under a split that prohibited cross-fold Tanimoto of 0.70 or greater weakens the explanation that the primary finding arose only from ordinary scaffold allocation. The rank correlation of matrix-dependent diversity estimates also shows that broad registry structure was partly preserved when the split mechanism changed.", "Normal"),
        ("The transfer was conditional rather than invariant. BACE showed almost no CAHit@3 change under the similarity-cluster split, normalized MRR was not uniformly lower, and interval exclusion shifted across endpoints. Split mechanism therefore changed both difficulty and the estimated magnitude of selection pressure. The appropriate claim is direction transport in three representative endpoints, not a universal law across targets, temporal splits, model registries or deployment populations.", "Normal"),
    ])
    doc.save(validate=False)
    print(UNPACKED)


if __name__ == "__main__":
    main()
