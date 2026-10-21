"""构建 Windows 与 macOS 可分发应用（可在 Linux / macOS / Windows 上运行本脚本，无需目标系统）。

产物（dist/）：
  QSB-Studio-Windows-x64.exe   单文件程序：内嵌独立 Python 运行时，双击即用
  QSB-Studio-macOS.zip         内含「QSB Studio.app」（同时内置 Apple 芯片与 Intel 两套运行时）

原理：应用求解与 Web 服务只用 Python 标准库，所以直接内置 python-build-standalone 的独立运行时即可，
不需要 PyInstaller，也不需要在目标系统上交叉编译。Windows 启动器用 Go 编写并交叉编译。

依赖：Python 3.9+、Go 1.21+（构建 Windows exe）、网络（首次下载运行时，之后缓存于 packaging/.cache）。
可选：llvm-rc + llvm-cvtres（给 exe 嵌入图标与版本信息；缺少时跳过）。

用法：python3 packaging/build.py [--only windows|macos] [--verify-linux]
  --verify-linux  额外用同样的裁剪规则打一个 Linux 运行时，并用它跑一遍测试，验证裁剪没删掉必需的库
"""
import argparse
import glob
import hashlib
import io
import os
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "packaging")
CACHE = os.path.join(PKG, ".cache")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, ROOT)
from app import VERSION  # noqa: E402

PBS_TAG = "20241016"
PY_VER = "3.12.7"
SHA256 = {
    "x86_64-pc-windows-msvc": "fa8ac308a7cd1774d599ad9a29f1e374fbdc11453b12a8c50cc4afdb5c4bfd1a",
    "aarch64-apple-darwin": "95dd397e3aef4cc1846867cf20be704bdd74edd16ea8032caf01e48f0c53d65d",
    "x86_64-apple-darwin": "848405b92bda20fad1f9bba99234c7d3f11e0b31e46f89835d1cb3d735e932aa",
    "x86_64-unknown-linux-gnu": "3a4d53a7ba3916c0c1f35cbbe57068e2571b138389f29cf5c35367fec8f4c617",
}

# 运行时裁剪：应用只用到标准库的一小部分，这些组件用不到
TRIM_STDLIB = ["test", "idlelib", "tkinter", "turtledemo", "turtle.py", "lib2to3", "ensurepip", "pydoc_data",
               "site-packages", "venv", "sqlite3", "doctest.py", "pydoc.py", "distutils",
               "msilib", "curses", "dbm", "xmlrpc", "wsgiref", "__phello__"]
TRIM_WIN = ["tcl", "include", "libs", "Scripts", "DLLs/tcl86t.dll", "DLLs/tk86t.dll", "DLLs/_tkinter.pyd",
            "DLLs/_sqlite3.pyd", "DLLs/sqlite3.dll", "DLLs/_ctypes_test.pyd", "DLLs/_ssl.pyd", "DLLs/_hashlib.pyd",
            "DLLs/libcrypto-3-x64.dll", "DLLs/libssl-3-x64.dll", "DLLs/_msi.pyd", "DLLs/winsound.pyd"]
TRIM_UNIX = ["include", "share", "lib/pkgconfig", "lib/tcl*", "lib/tk*", "lib/itcl*", "lib/thread*",
             "lib/libtcl*", "lib/libtk*",
             "bin/idle3", "bin/idle3.12", "bin/pip", "bin/pip3", "bin/pip3.12", "bin/pydoc3", "bin/pydoc3.12",
             "bin/2to3", "bin/2to3-3.12", "bin/python3-config", "bin/python3.12-config"]
TRIM_DYNLOAD = ["_tkinter", "_sqlite3", "_test", "_ctypes_test", "_xxtestfuzz", "xxlimited", "_ssl", "_hashlib",
                "_curses", "_dbm", "_gdbm"]


def log(*a):
    print("[build]", *a, flush=True)


def fetch(triple):
    os.makedirs(CACHE, exist_ok=True)
    name = f"cpython-{PY_VER}+{PBS_TAG}-{triple}-install_only_stripped.tar.gz"
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_TAG}/{name}"
        log("下载", url)
        with urllib.request.urlopen(url) as r, open(path + ".part", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(path + ".part", path)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != SHA256[triple]:
        raise SystemExit(f"{name} 校验失败：{h}")
    return path


def unpack_runtime(triple, dest):
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with tarfile.open(fetch(triple)) as tf:
        members = [m for m in tf.getmembers() if m.name.startswith("python/")]
        for m in members:
            m.name = m.name[len("python/"):]
        members = [m for m in members if m.name]
        if sys.version_info >= (3, 12):
            tf.extractall(dest, members=members, filter="tar")
        else:
            tf.extractall(dest, members=members)  # noqa: S202 — 来源已做 SHA256 校验
    windows = "windows" in triple
    stdlib = os.path.join(dest, "Lib") if windows else os.path.join(dest, "lib", "python3.12")
    for name in TRIM_STDLIB:
        _rm(os.path.join(stdlib, name))
    if windows:
        for name in TRIM_WIN:
            _rm(os.path.join(dest, name))
        for f in os.listdir(os.path.join(dest, "DLLs")):
            if f.startswith("_test"):
                _rm(os.path.join(dest, "DLLs", f))
    else:
        for name in TRIM_UNIX:
            for hit in glob.glob(os.path.join(dest, name)):
                _rm(hit)
        _rm(os.path.join(stdlib, "config-3.12-darwin"))
        _rm(os.path.join(stdlib, "config-3.12-x86_64-linux-gnu"))
        dyn = os.path.join(stdlib, "lib-dynload")
        for f in os.listdir(dyn):
            if any(f.startswith(p + ".") or f.startswith(p + "_") and p == "_test" for p in TRIM_DYNLOAD) \
                    or f.startswith("_test") or f.startswith("xxlimited"):
                _rm(os.path.join(dyn, f))
    # 去掉 __pycache__ 里的优化级 .pyc（保留普通 .pyc 以加快启动）
    for dp, dn, fn in os.walk(dest):
        for f in fn:
            if ".opt-" in f and f.endswith(".pyc"):
                os.remove(os.path.join(dp, f))
    return dest


def _rm(p):
    if os.path.islink(p) or os.path.isfile(p):
        os.remove(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)


def stage_app(dest, mac=False):
    """复制程序文件。mac=True 时附带原生窗口模块 native_mac.py 与内置的 rubicon-objc。"""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(os.path.join(dest, "qsb")); os.makedirs(os.path.join(dest, "static"))
    shutil.copy2(os.path.join(ROOT, "app.py"), dest)
    if mac:
        shutil.copy2(os.path.join(ROOT, "native_mac.py"), dest)
        shutil.copytree(os.path.join(ROOT, "vendor"), os.path.join(dest, "vendor"),
                        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(os.path.join(ROOT, "LICENSE"), dest)
    shutil.copy2(os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), dest)
    for f in os.listdir(os.path.join(ROOT, "qsb")):
        if f.endswith(".py"):
            shutil.copy2(os.path.join(ROOT, "qsb", f), os.path.join(dest, "qsb"))
    for f in os.listdir(os.path.join(ROOT, "static")):
        shutil.copy2(os.path.join(ROOT, "static", f), os.path.join(dest, "static"))
    return dest


def dir_size(p):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(p) for f in fn
               if not os.path.islink(os.path.join(dp, f)))


# ------------------------------------------------------------------ 图标
def png(size):
    return open(os.path.join(PKG, "icons", f"icon_{size}.png"), "rb").read()


def make_ico(path):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = [png(s) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    entries = b""
    for s, data in zip(sizes, imgs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), off)
        off += len(data)
    with open(path, "wb") as f:
        f.write(head + entries + b"".join(imgs))


def make_icns(path):
    types = [(b"icp4", 16), (b"icp5", 32), (b"icp6", 64), (b"ic07", 128), (b"ic08", 256), (b"ic09", 512),
             (b"ic10", 1024), (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512)]
    body = b"".join(t + struct.pack(">I", 8 + len(png(s))) + png(s) for t, s in types)
    with open(path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def windows_resource(out_syso):
    """生成 Go 链接器可用的 COFF 资源（图标 + 版本信息）。缺少 llvm 工具时返回 False。"""
    rc, cvt = shutil.which("llvm-rc"), shutil.which("llvm-cvtres")
    if not (rc and cvt):
        log("未找到 llvm-rc / llvm-cvtres，exe 将不带图标")
        return False
    tmp = os.path.join(BUILD, "res"); os.makedirs(tmp, exist_ok=True)
    make_ico(os.path.join(tmp, "app.ico"))
    v = ",".join((VERSION.split(".") + ["0"] * 4)[:4])
    rc_text = f"""#pragma code_page(65001)
1 ICON "app.ico"
1 VERSIONINFO
FILEVERSION {v}
PRODUCTVERSION {v}
FILEOS 0x40004
FILETYPE 0x1
BEGIN
  BLOCK "StringFileInfo"
  BEGIN
    BLOCK "080404B0"
    BEGIN
      VALUE "CompanyName", "JasonWod"
      VALUE "FileDescription", "QSB Studio 运筹学教学工作台"
      VALUE "FileVersion", "{VERSION}"
      VALUE "ProductName", "QSB Studio"
      VALUE "ProductVersion", "{VERSION}"
      VALUE "LegalCopyright", "MIT License"
      VALUE "OriginalFilename", "QSB-Studio.exe"
    END
  END
  BLOCK "VarFileInfo"
  BEGIN
    VALUE "Translation", 0x804, 1200
  END
END
"""
    with open(os.path.join(tmp, "app.rc"), "w", encoding="utf-8") as f:
        f.write(rc_text)
    subprocess.run([rc, "/c", "65001", "/fo", "app.res", "app.rc"], cwd=tmp, check=True)
    subprocess.run([cvt, "/machine:x64", f"/out:{out_syso}", "app.res"], cwd=tmp, check=True)
    return True


# ------------------------------------------------------------------ 打包
def zip_dir(zf, src, arc_prefix):
    for dp, dn, fn in os.walk(src):
        dn.sort()
        for f in sorted(fn):
            full = os.path.join(dp, f)
            arc = os.path.join(arc_prefix, os.path.relpath(full, src)).replace(os.sep, "/")
            zi = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                zi.external_attr = (stat.S_IFLNK | 0o755) << 16
                zi.create_system = 3
                zf.writestr(zi, os.readlink(full))
                continue
            zi.external_attr = (stat.S_IFREG | (0o755 if st.st_mode & 0o111 else 0o644)) << 16
            zi.create_system = 3
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(full, "rb") as fh:
                zf.writestr(zi, fh.read(), compresslevel=9)


def build_payload(runtime_triple, out_zip):
    stage = os.path.join(BUILD, f"payload-{runtime_triple}")
    unpack_runtime(runtime_triple, os.path.join(stage, "runtime"))
    stage_app(os.path.join(stage, "app"))
    with zipfile.ZipFile(out_zip, "w") as zf:
        zip_dir(zf, os.path.join(stage, "runtime"), "runtime")
        zip_dir(zf, os.path.join(stage, "app"), "app")
    pid = hashlib.sha256(open(out_zip, "rb").read()).hexdigest()[:12]
    log(f"载荷 {runtime_triple}: 解压后 {dir_size(stage) / 1e6:.1f} MB，压缩 {os.path.getsize(out_zip) / 1e6:.1f} MB，ID {pid}")
    return pid, stage


def go_build(goos, out, pid):
    env = dict(os.environ, GOOS=goos, GOARCH="amd64", CGO_ENABLED="0",
               GOFLAGS="-mod=mod", GOPROXY="off", GOSUMDB="off")   # 依赖源码在 launcher/third_party
    subprocess.run(["go", "build", "-trimpath", "-ldflags",
                    f"-s -w -X main.payloadID={pid}" + (" -H windowsgui" if goos == "windows" else ""),
                    "-o", out, "."], cwd=os.path.join(PKG, "launcher"), env=env, check=True)


def build_windows():
    launcher = os.path.join(PKG, "launcher")
    pid, _ = build_payload("x86_64-pc-windows-msvc", os.path.join(launcher, "payload.zip"))
    syso = os.path.join(launcher, "rsrc_windows_amd64.syso")
    windows_resource(syso)
    out = os.path.join(DIST, "QSB-Studio-Windows-x64.exe")
    try:
        go_build("windows", out, pid)
    finally:
        for f in (os.path.join(launcher, "payload.zip"), syso):
            if os.path.exists(f):
                os.remove(f)
    log(f"Windows: {out}（{os.path.getsize(out) / 1e6:.1f} MB）")
    return out


MAC_LAUNCHER = """#!/bin/bash
# QSB Studio 启动脚本：按芯片架构选择内置 Python，以原生窗口模式启动（失败时自动改用浏览器）
HERE="$(cd "$(dirname "$0")/.." && pwd)"
case "$(uname -m)" in
  arm64) PY="$HERE/Resources/python-arm64/bin/python3" ;;
  *)     PY="$HERE/Resources/python-x86_64/bin/python3" ;;
esac
export PYTHONDONTWRITEBYTECODE=1
exec "$PY" -I "$HERE/Resources/app/app.py" --native
"""

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>QSB Studio</string>
  <key>CFBundleDisplayName</key><string>QSB Studio</string>
  <key>CFBundleIdentifier</key><string>io.github.jasonwod.qsbstudio</string>
  <key>CFBundleVersion</key><string>{v}</string>
  <key>CFBundleShortVersionString</key><string>{v}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>QSBStudio</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleDevelopmentRegion</key><string>zh_CN</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSHumanReadableCopyright</key><string>MIT License · JasonWod</string>
</dict>
</plist>
"""

MAC_README = """QSB Studio for macOS
====================

1. 把「QSB Studio.app」拖到「应用程序」文件夹。
2. 第一次打开：本应用未经 Apple 公证，直接双击会提示「无法验证开发者」或「已损坏」。
   任选一种方法放行（只需一次）：
   · 在 Finder 里右键（或按住 Control 点按）应用 →「打开」→ 再点「打开」；
   · 或 macOS 15 及以上：先双击一次，再到「系统设置 → 隐私与安全性」底部点「仍要打开」；
   · 或在「终端」执行：xattr -dr com.apple.quarantine "/Applications/QSB Studio.app"
3. 打开后是一个独立窗口，用法和普通 Mac 应用一样：⌘W 关闭窗口即退出，⌘Q 退出，⌃⌘F 全屏。

支持 Apple 芯片（M 系列）与 Intel 芯片的 Mac，需要 macOS 11 或更高版本。
"""


def build_macos():
    app = os.path.join(BUILD, "mac", "QSB Studio.app")
    shutil.rmtree(os.path.dirname(app), ignore_errors=True)
    contents = os.path.join(app, "Contents")
    res = os.path.join(contents, "Resources")
    os.makedirs(os.path.join(contents, "MacOS")); os.makedirs(res)
    unpack_runtime("aarch64-apple-darwin", os.path.join(res, "python-arm64"))
    unpack_runtime("x86_64-apple-darwin", os.path.join(res, "python-x86_64"))
    stage_app(os.path.join(res, "app"), mac=True)
    make_icns(os.path.join(res, "AppIcon.icns"))
    exe = os.path.join(contents, "MacOS", "QSBStudio")
    with open(exe, "w", newline="\n") as f:
        f.write(MAC_LAUNCHER)
    os.chmod(exe, 0o755)
    with open(os.path.join(contents, "Info.plist"), "w", encoding="utf-8") as f:
        f.write(INFO_PLIST.format(v=VERSION))
    with open(os.path.join(contents, "PkgInfo"), "w") as f:
        f.write("APPL????")
    out = os.path.join(DIST, "QSB-Studio-macOS.zip")
    with zipfile.ZipFile(out, "w") as zf:
        zip_dir(zf, app, "QSB Studio.app")
        zi = zipfile.ZipInfo("使用说明.txt", date_time=(2026, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, MAC_README)
    log(f"macOS: {out}（{os.path.getsize(out) / 1e6:.1f} MB，.app 解压后 {dir_size(app) / 1e6:.1f} MB）")
    return out


def verify_linux():
    """用同一套裁剪规则构建 Linux 版启动器并实际运行：解压、启动、跑测试，验证裁剪没有误删。"""
    launcher = os.path.join(PKG, "launcher")
    pid, stage = build_payload("x86_64-unknown-linux-gnu", os.path.join(launcher, "payload.zip"))
    out = os.path.join(BUILD, "qsb-studio-linux-check")
    try:
        go_build("linux", out, pid)
    finally:
        os.remove(os.path.join(launcher, "payload.zip"))
    py = os.path.join(stage, "runtime", "bin", "python3")
    shutil.copytree(os.path.join(ROOT, "tests"), os.path.join(stage, "app", "tests"), dirs_exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "native_mac.py"), os.path.join(stage, "app"))   # 原生窗口流程测试需要
    r = subprocess.run([py, "-I", "-m", "unittest", "discover", "-s", "tests"], cwd=os.path.join(stage, "app"),
                       capture_output=True, text=True)
    log("裁剪后运行时跑测试：", r.stderr.strip().splitlines()[-1])
    if r.returncode:
        print(r.stderr[-3000:])
        raise SystemExit("裁剪后的运行时测试失败")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["windows", "macos"])
    ap.add_argument("--verify-linux", action="store_true")
    a = ap.parse_args()
    os.makedirs(DIST, exist_ok=True); os.makedirs(BUILD, exist_ok=True)
    if a.verify_linux:
        verify_linux()
    if a.only in (None, "windows"):
        build_windows()
    if a.only in (None, "macos"):
        build_macos()


if __name__ == "__main__":
    main()
