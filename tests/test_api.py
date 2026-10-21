"""API 与服务器测试：每个模块的示例可用且带演示帧；任意错误输入都返回友好提示而不是崩溃；静态文件安全。"""
import json
import logging
import os
import random
import sys
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qsb import api, modules  # noqa: E402

logging.getLogger("qsb").setLevel(logging.CRITICAL)   # 模糊测试会故意触发大量输入异常日志


def call(mid, payload):
    code, res = api.solve(mid, json.dumps(payload).encode())
    return code, res


class TestModules(unittest.TestCase):
    def test_all_ready(self):
        self.assertEqual(len(modules.MODULES), 19)
        self.assertEqual([m["id"] for m in modules.MODULES if m["status"] != "ready"], [])

    def test_default_examples_have_demo(self):
        for m in modules.MODULES:
            if m["id"] == "lp":
                continue
            payload = {f["id"]: f["value"] for f in m["form"]}
            code, res = call(m["id"], payload)
            self.assertEqual(code, 200, m["id"])
            self.assertNotEqual(res["status"], "error", (m["id"], res))
            self.assertGreaterEqual(len(res["steps"]), 3, m["id"])
            json.dumps(res, allow_nan=False)       # 必须是合法 JSON
            for f in res["steps"]:
                self.assertIn("title", f)
            for h in m["form"]:
                self.assertIn("help", h, f"{m['id']}.{h['id']} 缺少字段说明")

    def test_lp_endpoint(self):
        code, res = call("lp", {"obj": "max", "c": [3, 5], "A": [[1, 0], [0, 2], [3, 2]], "b": [4, 12, 18],
                                "senses": ["le", "le", "le"]})
        self.assertEqual(res["objective"], 36.0)
        self.assertIsNotNone(res["graph"])
        code, res = call("lp", {"obj": "max", "c": [1], "A": [[1, 2]], "b": [1], "senses": ["le"]})
        self.assertEqual(res["status"], "error")

    def test_bad_requests(self):
        self.assertEqual(api.solve("nope", b"{}")[0], 404)
        self.assertEqual(api.solve("lp", b"not json")[0], 400)
        self.assertEqual(api.solve("lp", b"[1,2]")[0], 400)
        self.assertEqual(api.solve("lp", b"x" * (api.MAX_BODY + 1))[0], 413)

    def test_fuzz_never_crashes(self):
        """随机打乱/删除/篡改各字段，结果只能是正常结果或 status=error，不能是 500。"""
        rng = random.Random(0)
        junk = ["", "abc", "-1", "1e400", [], [[]], [1, "x"], None, 0, "1,2\n3", "∞", "<script>", {"a": 1}, 10 ** 6]
        for m in modules.MODULES:
            base = {f["id"]: f["value"] for f in m["form"]} if m["id"] != "lp" else \
                {"obj": "max", "c": [1, 2], "A": [[1, 1]], "b": [4], "senses": ["le"]}
            for _ in range(40):
                p = dict(base)
                for k in rng.sample(list(p), k=rng.randint(1, len(p))):
                    if rng.random() < 0.3:
                        p.pop(k)
                    else:
                        p[k] = rng.choice(junk)
                code, res = call(m["id"], p)
                self.assertIn(code, (200,), (m["id"], p, res))
                json.dumps(res, allow_nan=False)


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app
        from http.server import ThreadingHTTPServer
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def get(self, path, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_static_and_api(self):
        code, body = self.get("/")
        self.assertEqual(code, 200); self.assertIn(b"QSB Studio", body)
        self.assertEqual(self.get("/app.js")[0], 200)
        self.assertEqual(json.loads(self.get("/api/health")[1])["modules"], 19)

    def test_path_traversal(self):
        for p in ["/../app.py", "/%2e%2e/app.py", "/..%2fapp.py", "/static/../../app.py"]:
            self.assertEqual(self.get(p)[0], 404, p)

    def test_host_header_check(self):
        self.assertEqual(self.get("/api/health", {"Host": "evil.example"})[0], 403)

    def test_cross_origin_post_rejected(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/solve/queue", data=b"{}", method="POST",
                                     headers={"Origin": "https://evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/solve/queue", data=b"{}", method="POST",
                                     headers={"Origin": f"http://127.0.0.1:{self.port}"})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 200)

    def test_post_solve(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/solve/queue",
                                     data=json.dumps({"method": "mm1", "lambda": 1, "mu": 2}).encode(), method="POST")
        with urllib.request.urlopen(req) as r:
            self.assertEqual(json.loads(r.read())["status"], "optimal")


if __name__ == "__main__":
    unittest.main()
