"""求解器正确性测试：教科书例题 + 与穷举 / 独立算法随机对拍。

运行：python3 -m unittest discover -s tests -v   （也兼容 pytest）
只依赖 Python 标准库。
"""
import itertools
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qsb import (assign, da, dp, forecast, gp, ilp, inventory, lp, maxflow, mst, nlp, pert, qp,  # noqa: E402
                 queue, shortest, sim, stats, transport, tsp)


def defaults(mod):
    return {f["id"]: f["value"] for f in mod.SPEC["form"]}


def head_number(r):
    """从 headline 里取「= 数字」。"""
    txt = r["headline"].split("=")[1].strip().split()[0].split("，")[0].split("[")[0]
    return float(txt)


# ---------------------------------------------------------------- LP 辅助：顶点枚举
def brute_lp(obj, c, A, b, senses):
    """枚举所有 n 条约束（含 x≥0）取等号的交点，取可行点中最优者。仅用于小规模、有界的测试问题。"""
    n = len(c)
    rows = [(A[i], b[i], senses[i]) for i in range(len(A))] + [([1.0 if k == j else 0.0 for k in range(n)], 0.0, "ge")
                                                             for j in range(n)]
    best = None
    for combo in itertools.combinations(range(len(rows)), n):
        M = [rows[i][0][:] + [rows[i][1]] for i in combo]
        try:   # 高斯消元
            for col in range(n):
                piv = max(range(col, n), key=lambda r: abs(M[r][col]))
                if abs(M[piv][col]) < 1e-10:
                    raise ZeroDivisionError
                M[col], M[piv] = M[piv], M[col]
                for r in range(n):
                    if r != col:
                        f = M[r][col] / M[col][col]
                        M[r] = [M[r][k] - f * M[col][k] for k in range(n + 1)]
            x = [M[i][n] / M[i][i] for i in range(n)]
        except ZeroDivisionError:
            continue
        ok = all(v >= -1e-7 for v in x)
        for a, bv, s in rows:
            lhs = sum(a[k] * x[k] for k in range(n))
            ok = ok and ((s == "le" and lhs <= bv + 1e-7) or (s == "ge" and lhs >= bv - 1e-7) or (s == "eq" and abs(lhs - bv) < 1e-7))
        if ok:
            z = sum(c[k] * x[k] for k in range(n))
            if best is None or (z > best if obj == "max" else z < best):
                best = z
    return best


class TestLP(unittest.TestCase):
    def test_textbook(self):
        r = lp.solve_lp("max", [3, 5], [[1, 0], [0, 2], [3, 2]], [4, 12, 18], ["le"] * 3, ["x1", "x2"])
        self.assertEqual(r["status"], "optimal")
        self.assertAlmostEqual(r["objective"], 36)
        self.assertEqual(r["solution"], {"x1": 2.0, "x2": 6.0})
        self.assertEqual(r["shadow_prices"], {"约束1": 0.0, "约束2": 1.5, "约束3": 1.0})

    def test_min_sign(self):
        r = lp.solve_lp("min", [2, 3], [[1, 1], [1, 2]], [4, 6], ["ge", "ge"], ["x1", "x2"])
        self.assertAlmostEqual(r["objective"], 10)
        self.assertAlmostEqual(r["objective_value_display"], 10)

    def test_degenerate_cycling_beale(self):
        """Beale 例：纯 Dantzig 规则会循环；现在应在有限步内得到最优 1.25。"""
        r = lp.solve_lp("max", [0.75, -20, 0.5, -6], [[0.25, -8, -1, 9], [0.5, -12, -0.5, 3], [0, 0, 1, 0]],
                        [0, 0, 1], ["le"] * 3, ["x1", "x2", "x3", "x4"])
        self.assertEqual(r["status"], "optimal")
        self.assertAlmostEqual(r["objective"], 1.25)
        self.assertLess(r["num_pivots"], 50)

    def test_infeasible_unbounded(self):
        self.assertEqual(lp.solve_lp("max", [1, 1], [[1, 1], [1, 1]], [1, 3], ["le", "ge"], ["a", "b"])["status"], "infeasible")
        self.assertEqual(lp.solve_lp("max", [1, 1], [[1, -1]], [1], ["le"], ["a", "b"])["status"], "unbounded")

    def test_negative_rhs_and_eq(self):
        r = lp.solve_lp("max", [1, 1], [[-1, -1], [1, 0]], [-2, 5], ["ge", "le"], ["a", "b"])   # x1+x2 ≤ 2
        self.assertAlmostEqual(r["objective"], 2)
        r = lp.solve_lp("max", [2, 3], [[1, 1], [1, 0]], [4, 3], ["eq", "le"], ["a", "b"])
        self.assertAlmostEqual(r["objective"], 12)

    def test_random_vs_vertex_enumeration(self):
        rng = random.Random(11)
        for _ in range(150):
            n, m = rng.randint(2, 3), rng.randint(1, 4)
            A = [[rng.randint(-3, 6) for _ in range(n)] for _ in range(m)]
            b = [rng.randint(-4, 12) for _ in range(m)]
            s = [rng.choice(["le", "le", "ge", "eq"]) for _ in range(m)]
            A += [[1 if k == j else 0 for k in range(n)] for j in range(n)]      # 加盒约束保证有界
            b += [10] * n; s += ["le"] * n
            obj = rng.choice(["max", "min"])
            c = [rng.randint(-5, 8) for _ in range(n)]
            ref = brute_lp(obj, c, A, b, s)
            r = lp.solve_lp(obj, c, A, b, s, [f"x{i}" for i in range(n)])
            if ref is None:
                self.assertEqual(r["status"], "infeasible", (obj, c, A, b, s))
            else:
                self.assertEqual(r["status"], "optimal", (obj, c, A, b, s))
                self.assertAlmostEqual(r["objective"], ref, places=5, msg=(obj, c, A, b, s))

    def test_validation(self):
        with self.assertRaises(lp.LPInputError):
            lp.solve_lp("max", [1, 2], [[1]], [1], ["le"], ["a", "b"])


class TestInteger(unittest.TestCase):
    def test_classic(self):
        r = ilp.solve(defaults(ilp))
        self.assertIn("x1=0 x2=5", r["headline"])
        self.assertGreater(len(r["steps"]), 3)

    def test_random_vs_enumeration(self):
        rng = random.Random(5)
        for _ in range(60):
            n = rng.randint(2, 3)
            cons = [[rng.randint(1, 6) for _ in range(n)] + [rng.randint(5, 20)] for _ in range(rng.randint(1, 3))]
            c = [rng.randint(1, 9) for _ in range(n)]
            types = [rng.choice("ibc") for _ in range(n)]
            p = {"obj": "max", "c": c, "constraints": "\n".join(",".join(map(str, r[:-1])) + f" <= {r[-1]}" for r in cons),
                 "types": types, "max_nodes": 2000}
            res = ilp.solve(p)
            if "c" in types:
                continue   # 混合整数难以穷举，仅检查不报错
            best = None
            ranges = [range(0, 2) if t == "b" else range(0, 21) for t in types]
            for x in itertools.product(*ranges):
                if all(sum(r[k] * x[k] for k in range(n)) <= r[-1] for r in cons):
                    z = sum(c[k] * x[k] for k in range(n))
                    best = z if best is None else max(best, z)
            self.assertAlmostEqual(float(res["headline"].split("目标值 = ")[1].split("（")[0]), best, msg=p)


class TestNonlinear(unittest.TestCase):
    def test_constrained(self):
        r = nlp.solve(defaults(nlp))
        x, y = (float(v) for v in r["headline"].split("(x, y) = (")[1].split(")")[0].split(","))
        self.assertAlmostEqual(x, 2, places=2); self.assertAlmostEqual(y, 2, places=2)

    def test_rosenbrock_bfgs(self):
        r = nlp.solve({"func": "rosenbrock", "constraints": "", "start": "-1.2, 1", "method": "bfgs"})
        self.assertIn("(1.0, 1.0)", r["headline"])

    def test_expression_safety(self):
        from qsb.report import InputError
        for bad in ["__import__('os').system('x')", "x.__class__", "open('f')", "[x for x in y]", "lambda: 1"]:
            with self.assertRaises(InputError):
                nlp.solve({"func": "custom", "expr": bad, "constraints": "", "start": "0,0"})

    def test_qp_kkt(self):
        r = qp.solve(defaults(qp))
        self.assertIn("(1.5, 1.5)", r["headline"])
        rng = random.Random(2)
        for _ in range(40):   # 随机凸 QP：与细网格搜索比较
            a, b_, cc = rng.uniform(0.5, 3), rng.uniform(-0.4, 0.4), rng.uniform(0.5, 3)
            Q = [[a, b_], [b_, cc]]
            c = [rng.uniform(-6, 2), rng.uniform(-6, 2)]
            cons = f"{rng.randint(1, 3)}, {rng.randint(1, 3)} <= {rng.randint(2, 8)}"
            res = qp.solve({"Q": Q, "c": c, "constraints": cons, "nonneg": "yes", "start": ""})
            fval = float(res["headline"].split("目标值 = ")[1])
            A = [float(t) for t in cons.split("<=")[0].split(",")]; bb = float(cons.split("<=")[1])
            f = lambda x, y: 0.5 * (a * x * x + 2 * b_ * x * y + cc * y * y) + c[0] * x + c[1] * y
            grid = min(f(i / 50, j / 50) for i in range(0, 451) for j in range(0, 451)
                       if A[0] * i / 50 + A[1] * j / 50 <= bb + 1e-9)
            self.assertLessEqual(fval, grid + 1e-3)   # headline 保留 4 位小数
            self.assertGreater(fval, grid - 0.05)

    def test_goal_programming(self):
        r = gp.solve(defaults(gp))
        self.assertIn("P3 偏差 2", r["headline"])
        r = gp.solve({"mode": "weighted", "hard": "1,1 <= 10", "goals": "1,2 >= 10 : under\n3,1 <= 12 : over"})
        self.assertIn("偏差 0", r["headline"])


class TestNetwork(unittest.TestCase):
    def test_transport_vs_lp(self):
        rng = random.Random(1)
        for _ in range(120):
            m, n = rng.randint(1, 4), rng.randint(1, 4)
            s = [rng.randint(0, 30) for _ in range(m)]; d = [rng.randint(0, 30) for _ in range(n)]
            if not sum(s) or not sum(d):
                continue
            C = [[rng.randint(1, 20) for _ in range(n)] for _ in range(m)]
            got = head_number(transport.solve({"supply": s, "demand": d, "cost": C}))
            S, D = sum(s), sum(d)
            ss, dd, CC = s[:], d[:], [r[:] for r in C]
            if S < D:
                ss.append(D - S); CC.append([0] * n)
            elif S > D:
                dd.append(S - D); CC = [r + [0] for r in CC]
            M, N = len(ss), len(dd)
            A = [[1 if k // N == i else 0 for k in range(M * N)] for i in range(M)] + \
                [[1 if k % N == j else 0 for k in range(M * N)] for j in range(N)]
            ref = lp.solve_lp("min", [CC[i][j] for i in range(M) for j in range(N)], A, ss + dd, ["eq"] * (M + N),
                              [f"v{k}" for k in range(M * N)])["objective"]
            self.assertAlmostEqual(got, ref, places=6)

    def test_assign_vs_bruteforce(self):
        rng = random.Random(3)
        for _ in range(120):
            nr, nc = rng.randint(1, 5), rng.randint(1, 5)
            C = [[rng.randint(0, 20) for _ in range(nc)] for _ in range(nr)]
            obj = rng.choice(["min", "max"])
            got = head_number(assign.solve({"obj": obj, "cost": C}))
            n = max(nr, nc)
            vals = [sum(C[i][p[i]] for i in range(nr) if p[i] < nc) for p in itertools.permutations(range(n))]
            self.assertAlmostEqual(got, min(vals) if obj == "min" else max(vals))

    def test_shortest_vs_floyd(self):
        rng = random.Random(4)
        for _ in range(60):
            n = rng.randint(2, 7)
            E = [(rng.randrange(n), rng.randrange(n), rng.randint(1, 15)) for _ in range(rng.randint(1, 14))]
            E = [e for e in E if e[0] != e[1]]
            if not E:
                continue
            directed = rng.choice(["yes", "no"])
            nn = max(max(u, v) for u, v, _ in E) + 1
            D = [[0 if i == j else math.inf for j in range(nn)] for i in range(nn)]
            for u, v, w in E:
                D[u][v] = min(D[u][v], w)
                if directed == "no":
                    D[v][u] = min(D[v][u], w)
            for k in range(nn):
                for i in range(nn):
                    for j in range(nn):
                        D[i][j] = min(D[i][j], D[i][k] + D[k][j])
            r = shortest.solve({"edges": "\n".join(f"{u} {v} {w}" for u, v, w in E), "source": 0, "target": nn - 1,
                                "directed": directed})
            if D[0][nn - 1] == math.inf:
                self.assertIn("无法到达", r["headline"])
            else:
                self.assertAlmostEqual(head_number(r), D[0][nn - 1])

    def test_mst_kruskal_equals_prim(self):
        rng = random.Random(6)
        for _ in range(60):
            n = rng.randint(2, 8)
            E = [(i, rng.randrange(i), rng.randint(1, 20)) for i in range(1, n)]          # 先保证连通
            E += [(rng.randrange(n), rng.randrange(n), rng.randint(1, 20)) for _ in range(rng.randint(0, 10))]
            E = [e for e in E if e[0] != e[1]]
            txt = "\n".join(f"{u} {v} {w}" for u, v, w in E)
            k = head_number(mst.solve({"edges": txt, "method": "kruskal"}))
            p = head_number(mst.solve({"edges": txt, "method": "prim"}))
            self.assertAlmostEqual(k, p)
            # 穷举 n−1 条边的子集验证最小
            best = math.inf
            for sub in itertools.combinations(E, n - 1):
                par = list(range(n))

                def f(a):
                    while par[a] != a:
                        a = par[a]
                    return a
                ok = True
                for u, v, _ in sub:
                    ru, rv = f(u), f(v)
                    if ru == rv:
                        ok = False; break
                    par[ru] = rv
                if ok:
                    best = min(best, sum(w for _, _, w in sub))
            self.assertAlmostEqual(k, best)

    def test_maxflow_vs_mincut(self):
        rng = random.Random(8)
        for _ in range(80):
            n = rng.randint(2, 7)
            E = [(rng.randrange(n), rng.randrange(n), rng.randint(1, 9)) for _ in range(rng.randint(1, 12))]
            E = [e for e in E if e[0] != e[1]]
            if not E:
                continue
            nn = max([n - 1] + [max(u, v) for u, v, _ in E]) + 1
            got = head_number(maxflow.solve({"edges": "\n".join(f"{u} {v} {w}" for u, v, w in E), "source": 0, "sink": n - 1}))
            cut = min(sum(w for u, v, w in E if (mask >> u) & 1 and not (mask >> v) & 1)
                      for mask in range(1 << nn) if mask & 1 and not (mask >> (n - 1)) & 1)
            self.assertAlmostEqual(got, cut)

    def test_tsp_exact_vs_bruteforce(self):
        rng = random.Random(9)
        for _ in range(40):
            n = rng.randint(2, 7)
            d = [[0 if i == j else rng.randint(1, 30) for j in range(n)] for i in range(n)]
            got = head_number(tsp.solve({"dist": d, "method": "exact"}))
            best = min(sum(d[t[i]][t[(i + 1) % n]] for i in range(n))
                       for t in ([0] + list(p) for p in itertools.permutations(range(1, n))))
            self.assertAlmostEqual(got, best)
            heur = head_number(tsp.solve({"dist": d, "method": "heuristic"}))
            self.assertGreaterEqual(heur, best - 1e-9)


class TestDecisionAndStats(unittest.TestCase):
    def test_knapsack_vs_bruteforce(self):
        rng = random.Random(10)
        for _ in range(60):
            items = [(rng.randint(1, 8), rng.randint(1, 15)) for _ in range(rng.randint(1, 8))]
            W = rng.randint(1, 20)
            r = dp.solve({"problem": "knapsack", "W": W, "items": "\n".join(f"{w}>{v}" for w, v in items)})
            best = max(sum(v for (w, v), t in zip(items, mask) if t) for mask in itertools.product([0, 1], repeat=len(items))
                       if sum(w for (w, _), t in zip(items, mask) if t) <= W)
            self.assertAlmostEqual(head_number(r), best)

    def test_stagecoach(self):
        r = dp.solve(dict(defaults(dp), problem="stagecoach"))
        self.assertTrue(r["headline"].endswith("= 11"))

    def test_decision(self):
        base = defaults(da)
        self.assertIn("EVPI = 26", da.solve(base)["headline"])
        self.assertIn("EVSI = 11", da.solve(dict(base, method="bayes"))["headline"])
        g = da.solve(dict(base, method="game", alts="R\nP\nS", states="R\nP\nS", payoff="0,-1,1\n1,0,-1\n-1,1,0"))
        self.assertIn("V = 0", g["headline"])
        self.assertEqual([row[1] for row in g["tables"][1]["rows"]], ["0.3333"] * 3)

    def test_queue_formulas(self):
        r = queue.solve({"method": "mmc", "lambda": 4, "mu": 3, "c": 2})
        self.assertIn("Lq = 1.0667", r["headline"])
        r = queue.solve({"method": "mm1", "lambda": 0.4, "mu": 0.6})
        self.assertIn("Lq = 1.3333", r["headline"])
        self.assertEqual(queue.solve({"method": "mm1", "lambda": 4, "mu": 3})["status"], "unstable")
        r = queue.solve({"method": "mmc", "lambda": 0.4, "mu": 0.6, "c": 1})      # c=1 不再被改成 2
        self.assertIn("M/M/1", r["headline"])

    def test_forecast_regression(self):
        s = [34, 36, 38, 39, 41, 40, 43, 45, 46, 48]
        r = forecast.solve({"series": s, "method": "regression"})
        n = len(s); t = range(1, n + 1); mt = (n + 1) / 2; ms = sum(s) / n
        b = sum((ti - mt) * (si - ms) for ti, si in zip(t, s)) / sum((ti - mt) ** 2 for ti in t)
        a = ms - b * mt
        self.assertIn(f"{round(a + b * (n + 1), 4)}", r["headline"])

    def test_inventory(self):
        self.assertIn("EOQ = 600", inventory.solve(defaults(inventory))["headline"])
        self.assertIn("103.6", inventory.solve(dict(defaults(inventory), method="news"))["headline"])

    def test_pert(self):
        r = pert.solve(defaults(pert))
        self.assertIn("1 → 2 → 4 → 6", r["headline"])
        self.assertIn("总工期 14", r["headline"])

    def test_stats_numerics(self):
        self.assertAlmostEqual(stats._t2p(1.96, 30), 0.0594, places=3)
        self.assertAlmostEqual(stats._tcrit(0.05, 9), 2.2622, places=3)
        self.assertAlmostEqual(stats._chi2crit(0.05, 3), 7.8147, places=3)
        for m in ["descriptive", "t1", "t2", "paired", "chisq", "corr"]:
            self.assertNotEqual(stats.solve(dict(defaults(stats), method=m))["status"], "error")
        # API 直接传字符串也要能用（原 bug：逐字符 float()）
        self.assertNotEqual(stats.solve({"method": "descriptive", "data1": "1, 2, 3"})["status"], "error")

    def test_sim_reproducible(self):
        a = sim.solve(defaults(sim)); b = sim.solve(defaults(sim))
        self.assertEqual(a["headline"], b["headline"])
        self.assertIn("平均等待", sim.solve(dict(defaults(sim), method="des", N=300))["headline"])


if __name__ == "__main__":
    unittest.main()
