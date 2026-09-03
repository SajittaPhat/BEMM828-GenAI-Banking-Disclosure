# Raw Questionnaire Data

The participant-level questionnaire dataset used in the dissertation is not included in this public repository.

For full local reproduction, the scripts expect the authorised workbook at:

```text
01_INPUTS/03_RAW_DATA/BEMM828_Questionnaire Data.xlsx
```

## Data protection

Do not commit the raw questionnaire workbook to a public GitHub repository.

The dataset contains participant-level questionnaire responses and is withheld from the public repository to protect research data and preserve the study's data-management boundaries.

## Integrity check

The executed workflow verifies the raw workbook using the SHA-256 checksum embedded in the analysis scripts before preparing or analysing the data.

## Derived participant-level files

Participant-level derived files generated during local analysis should also remain outside the public repository, including:

```text
agent_2_locked_raw_fields.csv
agent_2_locked_scores.csv
```

Only non-participant-level aggregate analytical outputs should be considered for public sharing, and only where appropriate.
