"""
app.py — QSB Studio 服务入口（纯 Python 标准库，无需安装任何第三方包）。

  GET  /api/health          健康检查
  GET  /api/modules         19 个模块的元数据（表单、说明）
  POST /api/solve/{mid}     求解，body 为该模块的 JSON payload
  GET  /api/ping            前端心跳（桌面模式据此判断页面是否还开着）
  POST /api/quit            桌面模式下退出程序
  GET  /                    前端静态页面（static/）

开发 / 课堂服务器：
    python3 app.py --port 8000                # 浏览器打开 http://127.0.0.1:8000
    python3 app.py --host 0.0.0.0 --port 8000 # 机房局域网共享（注意防火墙）

桌面模式（在默认浏览器中打开）：
    python3 app.py --desktop
  自动选端口、打开浏览器；已在运行时只打开浏览器；页面全部关闭约 3 分钟后自动退出。

原生窗口（打包后的应用使用）：
    python3 app.py --native                 # macOS：进程内创建 WKWebView 窗口，失败时回退到浏览器
    python3 app.py --embedded --port-file F # 供 Windows 启动器使用：只起服务，把端口写入 F，由启动器开 WebView2 窗口
"""
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
sys.path.insert(0, BASE)

from qsb import api  # noqa: E402

VERSION = "1.0.0"
log = logging.getLogger("qsb")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


class State:
    desktop = False         # 允许 /api/quit（桌面 / 窗口模式）
    mode = "server"         # server | browser | window（原生窗口内）
    on_quit = None          # 原生窗口模式下退出时回调（关闭窗口、结束事件循环）
    last_ping = time.time()
    seen_page = False
    server: ThreadingHTTPServer | None = None
    loopback = True
    stopped = threading.Event()   # 服务完全停止时置位


def _state_dir():
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support")
    else:
        root = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    d = os.path.join(root, "QSB Studio")
    os.makedirs(d, exist_ok=True)
    return d


class Handler(BaseHTTPRequestHandler):
    server_version = f"QSBStudio/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 走 logging，桌面版无控制台时写入日志文件
        log.debug("%s %s", self.address_string(), fmt % args)

    # ---- 工具 ----
    def _host_ok(self):
        """绑定在本机回环地址时，拒绝 Host 不是本机的请求（防 DNS 重绑定攻击）。"""
        if not State.loopback:
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1", "")

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def _read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > api.MAX_BODY:
            return None
        return self.rfile.read(n) if n > 0 else b""

    # ---- 路由 ----
    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"detail": "forbidden host"})
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            return self._json(*api.health())
        if path == "/api/modules":
            return self._json(*api.module_list())
        if path == "/api/ping":
            State.last_ping = time.time()
            if not State.seen_page:
                log.info("页面已连接（%s）", self.headers.get("User-Agent", "")[:120])
            State.seen_page = True
            return self._json(200, {"ok": True, "desktop": State.desktop, "mode": State.mode, "version": VERSION})
        if path.startswith("/api/"):
            return self._json(404, {"detail": "not found"})
        return self._static(path)

    do_HEAD = do_GET

    def _origin_ok(self):
        """跨站页面发来的 POST 会带上它自己的 Origin，一律拒绝（防止其他网站关闭程序或滥用求解接口）。"""
        origin = self.headers.get("Origin")
        if not origin:
            return True          # 非浏览器客户端（curl、脚本）不带 Origin
        return origin.rstrip("/") == f"http://{self.headers.get('Host', '')}"

    def do_POST(self):
        if not self._host_ok() or not self._origin_ok():
            return self._json(403, {"detail": "forbidden"})
        path = self.path.split("?", 1)[0]
        body = self._read_body()
        if body is None:
            return self._json(413, {"status": "error", "headline": "请求过大", "message": "请求体超过 512 KB。"})
        if path.startswith("/api/solve/"):
            mid = path[len("/api/solve/"):].strip("/")
            return self._json(*api.solve(mid, body))
        if path == "/api/quit" and State.desktop:
            self._json(200, {"ok": True})
            threading.Thread(target=_shutdown, daemon=True).start()
            return None
        return self._json(404, {"detail": "not found"})

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        full = os.path.realpath(os.path.join(STATIC, rel))
        if not full.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full):
            return self._send(404, "404 Not Found".encode(), "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, ctype)


def _shutdown():
    time.sleep(0.3)
    if State.on_quit:
        try:
            State.on_quit()
        except Exception:  # noqa: BLE001
            log.exception("退出回调失败")
    if State.server:
        State.server.shutdown()


PREFERRED_PORT = 47815      # 固定端口：浏览器存储按「协议+主机+端口」隔离，端口固定才能记住主题与上次输入


def _free_port(host):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _bind(host, port):
    """绑定端口；port=None 时先试固定端口，被占用再随机选。"""
    for p in ([port] if port else [PREFERRED_PORT, 0]):
        try:
            srv = ThreadingHTTPServer((host, p), Handler)
            srv.daemon_threads = True
            return srv
        except OSError as e:
            last = e
    raise last


def _existing_instance():
    """桌面模式单实例：若已有实例在运行，返回其 URL。"""
    try:
        with open(os.path.join(_state_dir(), "server.json"), encoding="utf-8") as f:
            info = json.load(f)
        url = f"http://127.0.0.1:{int(info['port'])}"
        with urllib.request.urlopen(url + "/api/health", timeout=1.5) as r:
            if json.loads(r.read()).get("service") == "qsb-studio":
                return url
    except Exception:  # noqa: BLE001
        return None
    return None


def _watchdog(idle_timeout, first_timeout):
    """页面关闭（心跳停止）一段时间后自动退出，避免后台残留进程。"""
    start = time.time()
    while True:
        time.sleep(5)
        now = time.time()
        if not State.seen_page and now - start > first_timeout:
            log.info("长时间没有页面连接，退出")
            break
        if State.seen_page and now - State.last_ping > idle_timeout:
            log.info("页面已关闭，退出")
            break
    _shutdown()


def _setup_logging(log_file, verbose):
    handlers = []
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers or [logging.NullHandler()])


def _write_state(port):
    with open(os.path.join(_state_dir(), "server.json"), "w", encoding="utf-8") as f:
        json.dump({"port": port, "pid": os.getpid(), "mode": State.mode}, f)


def _clear_state():
    try:
        os.remove(os.path.join(_state_dir(), "server.json"))
    except OSError:
        pass


def _serve():
    try:
        State.server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        State.server.server_close()
        State.stopped.set()


def main(argv=None):
    ap = argparse.ArgumentParser(description="QSB Studio 运筹学教学工作台")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机；0.0.0.0 可局域网访问）")
    ap.add_argument("--port", type=int, default=8000, help="端口（0 = 自动选择空闲端口）")
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    ap.add_argument("--desktop", action="store_true", help="桌面模式：在默认浏览器中打开，页面关闭后退出")
    ap.add_argument("--native", action="store_true", help="原生窗口模式（macOS）")
    ap.add_argument("--embedded", action="store_true", help="嵌入模式：供 Windows 原生窗口启动器调用")
    ap.add_argument("--port-file", default=None, help="嵌入模式下把实际端口写入该文件")
    ap.add_argument("--log-file", default=None, help="日志文件路径（桌面 / 原生模式默认写到用户数据目录）")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    app_mode = args.desktop or args.native or args.embedded
    _setup_logging(args.log_file or (os.path.join(_state_dir(), "qsb-studio.log") if app_mode else None), args.verbose)

    if args.native or args.embedded:
        State.desktop, State.mode = True, "window"
        try:
            State.server = _bind("127.0.0.1", None)
        except OSError as e:
            log.error("无法启动本地服务：%s", e)
            return 1
        port = State.server.server_address[1]
        url = f"http://127.0.0.1:{port}"
        log.info("QSB Studio %s 已启动（%s）：%s", VERSION, "原生窗口" if args.native else "嵌入模式", url)
        if args.embedded:
            if args.port_file:
                tmp = args.port_file + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(str(port))
                os.replace(tmp, args.port_file)
            # 兜底：启动器异常退出而窗口已不在时，心跳停止后自动退出
            threading.Thread(target=_watchdog, args=(180, 90), daemon=True).start()
            _serve()
            return 0
        threading.Thread(target=_serve, daemon=True).start()
        try:
            import native_mac
            native_mac.run(url, VERSION, BASE, State)          # 阻塞直到窗口关闭
            log.info("原生窗口已关闭，退出")
            State.server.shutdown()
            return 0
        except Exception:  # noqa: BLE001 — 原生窗口不可用时回退到浏览器
            log.exception("原生窗口启动失败，改用默认浏览器打开")
            State.mode = "browser"
            _write_state(port)
            threading.Thread(target=_watchdog, args=(180, 120), daemon=True).start()
            webbrowser.open(url)
            State.stopped.wait()
            _clear_state()
            return 0

    if args.desktop:
        url = _existing_instance()
        if url:
            log.info("已有实例在运行：%s", url)
            webbrowser.open(url)
            return 0
        State.desktop, State.mode = True, "browser"
        args.host, args.open = "127.0.0.1", True

    State.loopback = args.host in ("127.0.0.1", "localhost", "::1")
    try:
        State.server = _bind(args.host, None if args.desktop else (args.port or _free_port(args.host)))
    except OSError as e:
        log.error("无法监听 %s:%s（%s）。端口可能被占用，换一个 --port 试试。", args.host, args.port, e)
        return 1
    port = State.server.server_address[1]
    shown_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{shown_host}:{port}"
    log.info("QSB Studio %s 已启动：%s", VERSION, url)
    if State.desktop:
        _write_state(port)
        threading.Thread(target=_watchdog, args=(180, 120), daemon=True).start()
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        _serve()
    finally:
        if State.desktop:
            _clear_state()
    return 0


if __name__ == "__main__":
    sys.exit(main())
