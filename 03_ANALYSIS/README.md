# Analysis

This directory contains the reproducible analytical workflow used for the dissertation.

## Structure

```text
03_ANALYSIS/
├── README.md
├── code/
│   ├── README.md
│   ├── 01_data_audit.py
│   ├── 02_prepare_inputs.py
│   └── 03_statistical_analysis.py
└── outputs/
    └── README.md
```

## Workflow

The analysis should be run sequentially:

```text
01_data_audit.py
        ↓
02_prepare_inputs.py
        ↓
03_statistical_analysis.py
```

The first script audits the source data, the second prepares the locked input, and the third performs the statistical analysis.

Do not bypass the preparation stage by using workbook-derived composite variables as authoritative inputs.
