# R12.9 submission documents

This directory contains the synchronized Journal of Cheminformatics submission
layer generated on 15 August 2026.

## Manuscript files

- `manuscript_revised_submission_ready.docx`: clean English submission manuscript.
- `title_page.docx`: author and correspondence metadata.
- `declarations.docx`: availability, competing-interests, funding,
  contributions and acknowledgements statements.
- `Chinese_author_reference_topic_synchronized_R12.9.docx`: synchronized
  Chinese author-reference manuscript; it is not an upload file for the journal.

## Supplementary files

- `Additional_file_1_supplementary_methods.docx`: Supplementary Methods and
  Results, including editable Equations (1)–(22b).
- `Additional_file_2_supplementary_tables.xlsx`: 64-sheet machine-readable
  supplementary workbook.
- `Additional_file_3_supplementary_figures.pdf`: supplementary figures.
- `Additional_file_4_SHA256.txt`: checksum of the separately packaged code and
  reproducibility archive supplied with the submission.

Additional files 5–8 contain model-seed and temporal prediction partitions and
are supplied with the journal upload package. They are intentionally not stored
as ordinary Git objects in this repository.

## Figures and audits

`figures/` contains the eight final composite figures in embedded-font PDF,
editable SVG, and 600-dpi PNG. `audits/` contains the complete journal-format
audit and the formula/table/format audit. The formula audit reports 54 PASS and
0 FAIL checks; the complete submission audit reports 206 PASS, 0 FAIL, two
author actions and two external preview checks.

`figure_sources/` contains the final plotting and rebuild scripts, and
`source_data/` contains the machine-readable main-figure and main-table data
used by the submission layer.

The formula-only change does not modify any recorded outer score, prediction,
split, table value, figure value or retained negative result.
