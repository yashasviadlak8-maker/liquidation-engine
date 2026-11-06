# Paper progress: what each code milestone gives the paper

| Code milestone | Paper section | What to write once it's done |
|---|---|---|
| Rules spec verified | 2 Legal model | Cite s.45(2A), rates, set-off rules with primary sources |
| Problem formulation (step 3) | 3 Formulation | Already drafted in main.tex, keep in sync with code |
| tax.py, fifo.py + tests | 3 Formulation | Note integer-paise arithmetic, tests as validation |
| Baselines + brute force | 5 Baselines | Define pro-rata, FIFO-naive, and others |
| CP-SAT solver | 4 Method | Model, linearisation of set-off, solver settings |
| Brute-force agreement | 6 Results | Optimality evidence on small instances |
| Benchmark runs | 6 Results | Tax saved vs baselines by portfolio size and ST/LT mix |
| LLM comparison | 6 Results | FIFO violations, tax errors, optimality gap vs solver |
| Limitations | 7 | Single FY, no surcharge, no charges, equity only |

Rule: do not write a result into the paper until a test or script reproduces it.
Keep one script per table/figure under `experiments/`.


## Status
Done and reproducible: formulation, solver, brute-force validation, hard-instance evaluation (results/summary.csv).
Not done: LLM comparison (script ready, needs API key), real-portfolio case study, stronger practitioner baseline,
introduction/abstract, related work, primary-source verification of the three flagged rules.
