"""LLM vs exact solver on hard instances. NEEDS ANTHROPIC_API_KEY (not run in the build environment).
Run: ANTHROPIC_API_KEY=... python experiments/llm_vs_solver.py [n_instances]
Writes results/llm_eval.csv. Metrics per response: valid JSON, feasible, FIFO violation, claimed-tax error, optimality gap."""
import csv, random, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ai.llm import MODELS, get_client
from ai.llm_eval import build_prompt, score
from engine.instances import generate_hard_portfolio, generate_profile
from engine.rules import load_rules
from engine.solver import solve

client = get_client()
if client is None:
    sys.exit("Set ANTHROPIC_API_KEY to run this experiment.")
rules, SALE = load_rules(ROOT / "rules" / "fy2026_27.json"), date(2026, 11, 5)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
SYSTEM = "You are a careful Indian tax and portfolio assistant."
with open(ROOT / "results" / "llm_eval.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["seed", "condition", "valid_json", "feasible", "fifo_violation", "legal_tax", "claimed_tax_error", "optimality_gap", "optimum_tax"])
    for seed in range(N):
        pos, prof = generate_hard_portfolio(seed, n_positions=5, lots_per_position=3), generate_profile(seed)
        W = int(sum(p.price * p.total_qty for p in pos) * random.Random(seed).uniform(0.2, 0.5))
        opt = solve(pos, W, SALE, prof, rules).tax
        for cond, cot in (("zero_shot", False), ("chain_of_thought", True)):
            reply = client.complete(SYSTEM, build_prompt(pos, W, SALE, prof, cot), MODELS["eval"])
            s = score(reply, pos, W, SALE, prof, rules, opt)
            w.writerow([seed, cond, s["valid_json"], s["feasible"], s["fifo_violation"], s["legal_tax"],
                        s["claimed_tax_error"], s["optimality_gap"], opt])
            f.flush()
print("wrote results/llm_eval.csv")
