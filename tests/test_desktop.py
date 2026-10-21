"""桌面模式的看门狗：页面关闭（心跳停止）后服务应自动退出。"""
import os
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402


class TestWatchdog(unittest.TestCase):
    def _serve(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        app.State.server = srv
        t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        t.start()
        return srv, t

    def test_exit_when_no_page_ever_connects(self):
        srv, t = self._serve()
        app.State.seen_page = False
        orig = app.time.sleep
        app.time.sleep = lambda s: orig(0.05)          # 加速看门狗轮询
        try:
            threading.Thread(target=app._watchdog, args=(0.3, 0.3), daemon=True).start()
            t.join(timeout=5)
        finally:
            app.time.sleep = orig
        self.assertFalse(t.is_alive())
        srv.server_close()

    def test_exit_after_heartbeats_stop(self):
        srv, t = self._serve()
        app.State.seen_page = True
        app.State.last_ping = time.time()
        orig = app.time.sleep
        app.time.sleep = lambda s: orig(0.05)
        try:
            threading.Thread(target=app._watchdog, args=(0.4, 10), daemon=True).start()
            orig(0.2)
            self.assertTrue(t.is_alive())               # 心跳刚停，还不该退出
            t.join(timeout=5)
        finally:
            app.time.sleep = orig
        self.assertFalse(t.is_alive())
        srv.server_close()


class TestNativeMacFlow(unittest.TestCase):
    """在模拟的 Objective-C 环境中走完 native_mac.run 的流程，捕捉拼写 / 调用顺序等 Python 层错误。
    真正的 Cocoa 行为由 CI 中的 macOS 冒烟测试验证。"""

    def test_run_with_fake_objc(self):
        import types
        from unittest import mock
        fake = types.ModuleType("rubicon.objc")
        calls = []

        class Obj(mock.MagicMock):
            def __getattr__(self, name):
                calls.append(name)
                return super().__getattr__(name)

        class NSObject:
            @classmethod
            def alloc(cls):
                return cls()

            def init(self):
                return self

        fake.ObjCClass = lambda name: Obj(name=name)
        fake.NSObject = NSObject
        fake.objc_method = lambda f: f
        fake.SEL = lambda s: s
        fake.send_message = lambda *a, **k: None
        fake.ns_from_py = lambda v: v
        fake.objc_id = object
        runtime = types.ModuleType("rubicon.objc.runtime"); runtime.load_library = lambda n: None
        tps = types.ModuleType("rubicon.objc.types")
        tps.NSMakeRect = lambda *a: a; tps.NSMakeSize = lambda *a: a
        pkg = types.ModuleType("rubicon"); pkg.objc = fake
        state = types.SimpleNamespace(on_quit=None)
        with mock.patch.dict(sys.modules, {"rubicon": pkg, "rubicon.objc": fake, "rubicon.objc.runtime": runtime,
                                           "rubicon.objc.types": tps}), mock.patch.object(sys, "platform", "darwin"):
            import native_mac
            native_mac.run("http://127.0.0.1:1", "1.0", os.path.dirname(os.path.abspath(app.__file__)), state)
        self.assertIn("run", calls)                      # 事件循环被启动
        self.assertIn("setMainMenu_", calls)
        self.assertIn("loadRequest_", calls)
        self.assertTrue(callable(state.on_quit))


if __name__ == "__main__":
    unittest.main()
