# Judge calibration

This document records the calibration procedure for the LLM-judge in `evals/judge.py`.

## Why calibrate

A pass/fail verdict from an LLM-judge is only as trustworthy as its agreement with humans.
Without a calibration check, a "judge says 0.9" number is decoration. We measure
agreement against a human-labeled reference set and target Cohen's κ ≥ 0.7.

## Procedure

1. Take 20 scorecards drawn from the eval suite (mix of strong and weak runs).
2. Label each scorecard manually on the same `verdict ∈ {pass, borderline, fail}` scale,
   using the same definitions the judge prompt uses (see `judge.py`).
3. Run the judge on the same 20 scorecards.
4. Compute Cohen's κ between human and judge labels.

The script `evals/calibrate_judge.py` automates step 3–4 against any directory of
scorecard JSON files plus a `human_labels.csv` (columns: `id, verdict`).

## Latest measurement

> The first calibration is run after the first live demo populates `examples/`.
> Until then, the judge is informational only. Update this section with:
>
> - **Date:** YYYY-MM-DD
> - **Sample size:** N
> - **Cohen's κ:** 0.XX
> - **Confusion matrix** (rows = human, cols = judge):
>
> |       | pass | borderline | fail |
> |-------|------|------------|------|
> | pass  |      |            |      |
> | borderline |  |            |      |
> | fail  |      |            |      |
>
> - **Notes:** any patterns in disagreement, prompt edits, model swaps.

## Why κ ≥ 0.7

Landis and Koch (1977) call κ in [0.61, 0.80] "substantial agreement." For a
demo-grade research assistant, that's the bar above which the judge is useful as
a pre-filter. Below that, treat its score as advisory only.
