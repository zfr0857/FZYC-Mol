# Reproducibility scope

The quick entry point recomputes manuscript-facing checks and Figure 7 from
the checked machine-readable exports without refitting molecular models. The
full entry point stages data, split, classical, frozen-representation and
locked D-MPNN workflows. Failure and exclusion records remain available in
`FAILURE_AND_EXCLUSION_LOG_INDEX.csv` and the verification logs.

The recorded downstream times include inner and outer downstream fit/predict
time. They exclude model acquisition, encoder pretraining and cached embedding
extraction. This boundary is identical to the manuscript definition.
