BEMM828 GenAI Banking Disclosure Analysis
This repository contains the reproducible Python code used for the data audit, input preparation and statistical analysis supporting an MSc Business Analytics dissertation at the University of Exeter Business School.
Dissertation title
Customer Information Disclosure to Generative AI Banking Assistants: The Roles of Perceived Transparency and Privacy Concerns
Research focus
The study examines how perceived transparency and privacy concerns are associated with customers' willingness to disclose personal information to a hypothetical generative AI banking assistant, with customer trust modelled as the single statistical mediator.
The analysis uses a primary quantitative, scenario-based questionnaire completed by adults who use digital banking in the United Kingdom.
Repository structure
```text
.
├── README.md
├── requirements.txt
├── .gitignore
├── 01_INPUTS/
│   ├── README.md
│   ├── 01_CHAPTERS_1_TO_3/
│   │   └── README.md
│   ├── 02_QUESTIONNAIRE_AND_CODEBOOK/
│   │   └── README.md
│   └── 03_RAW_DATA/
│       └── README.md
└── 03_ANALYSIS/
    ├── README.md
    ├── code/
    │   ├── README.md
    │   ├── 01_data_audit.py
    │   ├── 02_prepare_inputs.py
    │   └── 03_statistical_analysis.py
    └── outputs/
        └── README.md
```
Analysis workflow
Run the scripts in this order:
`03_ANALYSIS/code/01_data_audit.py`
`03_ANALYSIS/code/02_prepare_inputs.py`
`03_ANALYSIS/code/03_statistical_analysis.py`
1. Data audit
`01_data_audit.py` verifies:
raw workbook integrity through SHA-256 checking
workbook schema
questionnaire variable mapping
response coding
eligibility fields
missingness
duplicate-response diagnostics
construct-level invariant-response diagnostics
This script does not test the research hypotheses.
2. Input preparation
`02_prepare_inputs.py`:
verifies the raw workbook checksum
reads only the authorised raw questionnaire fields
excludes workbook-derived composite variables from substantive analysis
excludes the `Scale_Checks` worksheet as an authoritative results source
writes the locked analysis input used by the statistical script
records source and software-session information
3. Statistical analysis
`03_statistical_analysis.py` performs:
ordinal measurement diagnostics using polychoric correlations
reliability and validity assessment
locked construct scoring
descriptive statistics and construct correlations
observed-score path analysis
bias-corrected bootstrap indirect-effect analysis with 5,000 resamples
robustness analysis using age band and prior AI or bank chatbot use
diagnostic sensitivity analysis excluding construct-level invariant-response cases
The primary bootstrap seed is `82852026`. The diagnostic sensitivity bootstrap uses `82852027`.
Locked construct scoring
The public release preserves the scoring used in the dissertation analysis.
Perceived transparency: equally weighted mean across Disclosure, Clarity and Accuracy dimension scores.
Privacy concerns: equally weighted mean across Control, Awareness and Collection dimension scores.
Customer trust: equally weighted mean across Competence, Benevolence and Integrity dimension scores.
Willingness to disclose: mean of the four WTD items.
The Privacy score is a project composite across the three source dimensions and is not presented as a newly validated second-order latent construct.
Hypothesis model
The statistical model evaluates:
H1: Privacy concerns -> Willingness to disclose
H2: Perceived transparency -> Customer trust
H3: Privacy concerns -> Customer trust
H4: Customer trust -> Willingness to disclose
H5: Perceived transparency -> Customer trust -> Willingness to disclose
H6: Privacy concerns -> Customer trust -> Willingness to disclose
The direct Transparency -> Willingness to disclose path is retained as exploratory rather than as a hypothesis.
Data availability
Participant-level questionnaire data are not included in this public repository.
The public repository contains analytical code and documentation only. Full local reproduction requires access to the authorised research dataset and source documents, which must be placed locally in the expected `01_INPUTS` directories.
No participant-level raw or derived dataset should be committed to the public repository.
Reproducibility boundary
The analytical chain used in the dissertation is:
```text
RAW DATA -> CODE -> ANALYTICAL OUTPUT -> DISSERTATION RESULTS
```
The public-release scripts preserve the statistical logic of the executed dissertation analysis. Public-release changes are limited to file naming, documentation and terminology clarification and must not alter scoring formulas, hypotheses, exclusion rules, random seeds, bootstrap procedures or statistical calculations.
Interpretation boundary
The study uses cross-sectional questionnaire data.
Reported relationships are associations rather than causal effects.
Indirect effects are statistical indirect associations and are not evidence of causal mediation.
Willingness to disclose represents stated intention in a hypothetical scenario rather than observed disclosure behaviour.
The retained non-probability sample should not be interpreted as representative of all UK digital banking customers.
Requirements
Install the required Python packages with:
```bash
pip install -r requirements.txt
```
See `03_ANALYSIS/code/README.md` for the expected run order and local input requirements.
Data protection
Do not upload the raw questionnaire workbook, participant-level derived files, dissertation source documents or other research records containing non-public material to this repository.
