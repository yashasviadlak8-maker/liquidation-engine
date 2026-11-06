"""Main evaluation on hard synthetic instances (gains-heavy, boundary lots, YTD gains, b/f losses).
Writes results/hard_instances.csv, results/summary.csv and paper/results_table.tex.
Run in time-boxed chunks (rows are appended, seeds resume):
  python experiments/evaluate.py run <size_index> <budget_seconds>
  python experiments/evaluate.py summary"""
import csv, random, sys, time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.baselines import greedy_tax_aware, largest_first, pro_rata
from engine.instances import generate_hard_portfolio, generate_profile
from engine.plan import evaluate_plan
from engine.rules import load_rules
from engine.solver import solve

rules = load_rules(ROOT / "rules" / "fy2026_27.json")
SALE = date(2026, 11, 5)
SIZES = [(5, 3, 100), (12, 4, 40), (25, 4, 15)]      # (positions, lots/position, instances)
METHODS = ["solver", "greedy", "pro_rata", "largest_first"]
out = ROOT / "results" / "hard_instances.csv"


COLS = ["positions", "lots", "seed", "withdraw_pct", "tax_optimal", "tax_s"] + [m + "_tax" for m in METHODS]


def run(idx, budget):
    n, lp, N = SIZES[idx]
    done = [r for r in csv.DictReader(open(out))] if out.exists() else []
    start = sum(int(r["positions"]) == n for r in done)
    new = not out.exists()
    t_start = time.time()
    with open(out, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(COLS)
        for seed in range(start, N):
            if time.time() - t_start > budget:
                break
            pos = generate_hard_portfolio(seed, n_positions=n, lots_per_position=lp)
            prof = generate_profile(seed)
            total = sum(p.price * p.total_qty for p in pos)
            pct = random.Random(seed).uniform(0.2, 0.5)
            W = int(total * pct)
            r = solve(pos, W, SALE, prof, rules, time_limit=30, workers=4)
            ev = lambda x: evaluate_plan(pos, x, SALE, prof, rules).tax
            g = ev(greedy_tax_aware(pos, W, SALE, prof, rules, chunk_value=max(500_000, W // 50)))
            w.writerow([n, n * lp, seed, round(pct, 3), int(r.tax_optimal), round(r.tax_seconds, 3), r.tax, g,
                        ev(pro_rata(pos, W)), ev(largest_first(pos, W))])
            f.flush()
    print(f"size {n}x{lp}: {seed - start + (0 if time.time() - t_start > budget else 1)} instances this call", flush=True)


def summary():
    rows = list(csv.DictReader(open(out)))
    summ = [["lots", "instances", "solver_s_mean", "solver_s_max", "optimal_pct"] +
            [f"{m}_mean_tax" for m in METHODS] + [f"{m}_subopt_pct" for m in METHODS[1:]] + [f"{m}_mean_excess" for m in METHODS[1:]]]
    for n, lp, _ in SIZES:
        rs = [r for r in rows if int(r["positions"]) == n]
        k = len(rs)
        if not k:
            continue
        tx = {m: [int(r[m + "_tax"]) for r in rs] for m in METHODS}
        st = [float(r["tax_s"]) for r in rs]
        summ.append([n * lp, k, round(sum(st) / k, 2), round(max(st), 2),
                     round(100 * sum(r["tax_optimal"] == "1" for r in rs) / k, 1)]
                    + [round(sum(tx[m]) / k / 100) for m in METHODS]
                    + [round(100 * sum(a > b for a, b in zip(tx[m], tx["solver"])) / k, 1) for m in METHODS[1:]]
                    + [round(sum(a - b for a, b in zip(tx[m], tx["solver"])) / k / 100) for m in METHODS[1:]])
    with open(ROOT / "results" / "summary.csv", "w", newline="") as f:
        csv.writer(f).writerows(summ)
    ix = {h: i for i, h in enumerate(summ[0])}
    tex = ["\\begin{tabular}{rrrrrrr}", "\\hline",
           "Lots & Inst. & Solver (s) & Greedy subopt.\\% & Greedy excess (Rs) & Pro-rata excess (Rs) & Largest-first excess (Rs) \\\\", "\\hline"]
    for r in summ[1:]:
        tex.append(f"{r[ix['lots']]} & {r[ix['instances']]} & {r[ix['solver_s_mean']]} & {r[ix['greedy_subopt_pct']]} & "
                   f"{r[ix['greedy_mean_excess']]:,} & {r[ix['pro_rata_mean_excess']]:,} & {r[ix['largest_first_mean_excess']]:,} \\\\")
    tex += ["\\hline", "\\end{tabular}"]
    (ROOT / "paper" / "results_table.tex").write_text("\n".join(tex) + "\n")
    for r in summ:
        print(r)


if __name__ == "__main__":
    summary() if sys.argv[1] == "summary" else run(int(sys.argv[2]), float(sys.argv[3]))
