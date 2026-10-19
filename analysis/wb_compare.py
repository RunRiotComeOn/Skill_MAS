"""Paired comparison of WorkBench runs: accuracy, side effects, exact McNemar p-values."""
import json, sys
from math import comb
from pathlib import Path

root = Path(sys.argv[1]); names = sys.argv[2:]
runs = {}
for n in names:
    runs[n] = {json.loads(p.read_text())["uid"]: json.loads(p.read_text()) for p in (root / n / "tasks").glob("*.json")}
common = sorted(set.intersection(*(set(r) for r in runs.values())))
print(f"paired tasks: {len(common)}")
for n in names:
    rs = [runs[n][u] for u in common]
    acc = sum(r["correct"] for r in rs) / len(rs); se = sum(r["side_effects"] for r in rs) / len(rs)
    cost = sum(float(r.get("usage", {}).get("estimated_cost_usd", 0)) for r in rs)
    print(f"{n:22s} acc={acc:.3f} side_effects={se:.3f} cost=${cost:.2f}")

def mcnemar(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

for i, a in enumerate(names):
    for bname in names[i + 1:]:
        b = sum(runs[a][u]["correct"] and not runs[bname][u]["correct"] for u in common)
        c = sum(runs[bname][u]["correct"] and not runs[a][u]["correct"] for u in common)
        print(f"{a} vs {bname}: {a}-only={b} {bname}-only={c} McNemar p={mcnemar(b, c):.4f}")
