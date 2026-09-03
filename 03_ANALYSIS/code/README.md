# Python Analysis Code

This directory contains the three Python scripts used in the dissertation analytical workflow.

## Run order

Run the scripts from the repository using the following order:

```bash
python 03_ANALYSIS/code/01_data_audit.py
python 03_ANALYSIS/code/02_prepare_inputs.py
python 03_ANALYSIS/code/03_statistical_analysis.py
```

## 1. `01_data_audit.py`

Purpose:

- verify the raw workbook checksum
- inspect workbook structure
- compare questionnaire/codebook variable identifiers with workbook columns
- validate response coding
- audit missingness and focal-item completeness
- identify duplicate-response patterns
- identify construct-level invariant-response patterns as diagnostic flags

This script performs no substantive hypothesis testing.

## 2. `02_prepare_inputs.py`

Purpose:

- re-verify the raw workbook checksum
- extract only the authorised raw fields
- exclude workbook-derived composite fields
- exclude the `Scale_Checks` worksheet as an authoritative results source
- write the locked raw-field extract used by the statistical script
- preserve source and software-session information

## 3. `03_statistical_analysis.py`

Purpose:

- construct the polychoric item-correlation matrix
- perform limited-information ordinal measurement diagnostics
- calculate reliability and validity diagnostics
- write the scoring lock
- generate construct scores
- produce descriptives and correlations
- estimate the observed-score path models
- estimate H5 and H6 indirect associations using 5,000 bias-corrected bootstrap resamples
- run the authorised robustness analysis
- run the diagnostic sensitivity analysis

## Local input files required

For full reproduction, the following non-public local files must exist:

```text
01_INPUTS/03_RAW_DATA/BEMM828_Questionnaire Data.xlsx
01_INPUTS/02_QUESTIONNAIRE_AND_CODEBOOK/BEMM828_Questionnaire_Only_Qualtrics_Build.docx
01_INPUTS/01_CHAPTERS_1_TO_3/Chapters 1-3_030926.docx
```

## Important reproducibility note

The public repository version should preserve the executed analytical logic. Changes made for public release should be limited to documentation, safe file naming and terminology clarification.

Do not change:

- construct-item mappings
- scoring formulas
- hypothesis definitions
- primary sample rules
- diagnostic sensitivity rules
- bootstrap resample count
- random seeds
- model specification

without clearly documenting that the code is no longer the dissertation analysis.
