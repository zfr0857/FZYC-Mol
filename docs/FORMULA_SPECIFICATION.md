# Formula specification

This document fixes the mathematical notation used by the submission and links
the displayed equations to `docs/Equation_to_code_mapping.csv`. All displayed
equations in the manuscript are editable Office Math objects. Symbols in table
cells remain formatted Unicode text so that Word, WPS and LibreOffice preserve
the symbol column.

## Primary estimands

For outer audit unit `u = (s, f)` and eligible prefix `C_K`, the
validation-selected candidate is

`j_hat_u(K) = arg max_{j in C_K} V(u,j)`.

The K-invariant full-registry reference maximizes the mean outer-audit utility
over units whose split seed is not `s`, with the search restricted to `C_32`.
The K-dependent within-prefix reference uses the same leave-one-split-seed-out
mean but restricts the search to `C_K`.

The three primary gaps are

- `G_inv(u,K) = A(u,j_ref^inv(-s)) - A(u,j_hat_u(K))`;
- `G_dep(u,K) = A(u,j_ref^dep(-s,K)) - A(u,j_hat_u(K))`;
- `G_avail(u,K) = A(u,j_ref^inv(-s)) - A(u,j_ref^dep(-s,K))`.

The identity `G_inv = G_avail + G_dep` holds at unrounded machine precision.
The split-seed mean first averages outer folds within a split seed. The endpoint
contrast then averages the split-seed-level differences between `K = 32` and
`K = 4`; it does not pool classification ROC-AUC and regression RMSE values on a
single numerical scale.

## Supplementary numbering

The supplementary equations are numbered (1) through (22b). Lettered numbers
identify separate displayed definitions, not unnumbered continuations. The
canonical mapping includes entries for (5a), (5b), (10a), (10b), (12a), (12b),
(17a), (17b), (18a), (18b), (19a), (19b), (20a), (20b), (22a) and (22b).

## Rendering policy

- Display equations use native editable OMML and Cambria Math.
- Mathematical variables are italic; multi-letter operators and descriptive
  subscripts are upright.
- Fractions, summations, limits, hats, bars and superscripts use structured
  math elements rather than slash-separated prose.
- Equation numbers are right-aligned with tab stops and no manual page breaks.
- Table 3 symbols use ordinary text runs with explicit font and subscript
  formatting to avoid empty formula objects in LibreOffice.
