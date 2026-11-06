# liquidation-engine

Given a client's holdings (lots per scrip per demat account) and a withdrawal amount, find the sell plan with the
minimum capital-gains tax under Indian rules, with FIFO enforced per demat account (s.45(2A), Income Tax Act 1961).
Lot choice is not a decision variable: the decision is how many shares to sell per position. The solver is exact
(CP-SAT) and is validated against exhaustive search. AI is used only at the edges (see below); it never decides.

## Run
    pip install -r requirements.txt
    python -m pytest -q                       # 196 tests
    uvicorn api.main:app --reload             # open http://localhost:8000
    # or: docker build -t planner . && docker run -p 8000:8000 planner
Optional: set `ANTHROPIC_API_KEY` (see `.env.example`) to enable LLM request parsing and explanations.

## Layout
- `engine/`  pure Python, no I/O, no AI. Integer paise. `tax.py` `fifo.py` `plan.py` `baselines.py` `bruteforce.py` `solver.py` `instances.py`
- `rules/`   versioned tax parameters (JSON). `docs/rules_spec.md` has verification status of every rule.
- `ingest/`  deterministic tradebook CSV -> FIFO lots -> positions (+ holdings reconciliation)
- `ai/`      `intent.py` (text -> constraints, echo-back), `explain.py` (numbers verified against the plan),
             `ingest_llm.py` (grounded extraction from messy statements), `rules_watch.py` (proposes rule diffs, human-approved),
             `llm_eval.py` (LLM-vs-solver scoring)
- `api/`     FastAPI: `/api/plan`, `/api/ingest`, `/api/parse-request`, `/api/sample`
- `web/`     single-page UI served at `/`
- `experiments/` reproducible scripts; `results/` outputs; `paper/` LaTeX draft written alongside the code

## AI guardrails
Every LLM output is schema-validated and checked deterministically (grounding in source text, numeric faithfulness,
known symbols, echo-back confirmation) and every feature has a non-AI fallback. The rules watcher only writes
`rules/proposed_*.json`; a human reviews it and the tests must pass before it becomes a live rules file.

## Reproduce results
    python experiments/evaluate.py run 0 240; python experiments/evaluate.py run 1 240; python experiments/evaluate.py run 2 240
    python experiments/evaluate.py summary    # writes results/summary.csv and paper/results_table.tex
    ANTHROPIC_API_KEY=... python experiments/llm_vs_solver.py   # not yet run

## Known limits (v1)
Listed equity, one financial year, no surcharge, brokerage or STT, no splits/bonuses in ingestion, prices supplied by the user.
Tradebook column names are assumed Zerodha-style; test with real exports. Three tax rules still need primary-source verification (docs/rules_spec.md).
This is a planning aid, not tax or investment advice.
