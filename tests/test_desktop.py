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


if __name__ == "__main__":
    unittest.main()
