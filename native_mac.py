"""macOS 原生窗口：在本进程内用 WKWebView 显示 QSB Studio（通过内置的 rubicon-objc 调用系统 API）。

由 app.py --native 调用：run(url, version, base, State)，阻塞运行 Cocoa 事件循环；关闭最后一个窗口即退出程序。
任何一步失败都会抛出异常，app.py 捕获后回退到默认浏览器。
"""
import logging
import os
import sys

log = logging.getLogger("qsb")

NSWindowStyleMaskTitled = 1 << 0
NSWindowStyleMaskClosable = 1 << 1
NSWindowStyleMaskMiniaturizable = 1 << 2
NSWindowStyleMaskResizable = 1 << 3
NSBackingStoreBuffered = 2
NSViewWidthSizable = 1 << 1
NSViewHeightSizable = 1 << 4
NSApplicationActivationPolicyRegular = 0
NSEventModifierFlagShift = 1 << 17
NSEventModifierFlagControl = 1 << 18
NSEventModifierFlagOption = 1 << 19
NSEventModifierFlagCommand = 1 << 20


def _menu(objc, title, items):
    """items: [(标题, 选择器, 快捷键, 修饰键或 None)]，None 项表示分隔线。"""
    NSMenu, NSMenuItem = objc.ObjCClass("NSMenu"), objc.ObjCClass("NSMenuItem")
    menu = NSMenu.alloc().initWithTitle_(title)
    for it in items:
        if it is None:
            menu.addItem_(NSMenuItem.separatorItem())
            continue
        text, sel, key, mods = it
        mi = menu.addItemWithTitle_action_keyEquivalent_(text, objc.SEL(sel), key)
        if mods is not None:
            mi.setKeyEquivalentModifierMask_(mods)
    holder = NSMenuItem.alloc().init()
    holder.setSubmenu_(menu)
    return holder


def run(url, version, base, state):
    if sys.platform != "darwin":
        raise RuntimeError("原生窗口仅支持 macOS")
    sys.path.insert(0, os.path.join(base, "vendor"))
    from rubicon import objc
    from rubicon.objc import NSObject, objc_method
    from rubicon.objc.runtime import load_library
    from rubicon.objc.types import NSMakeRect, NSMakeSize

    load_library("AppKit")
    load_library("WebKit")
    NSApplication = objc.ObjCClass("NSApplication")
    NSWindow = objc.ObjCClass("NSWindow")
    NSImage = objc.ObjCClass("NSImage")
    NSURL = objc.ObjCClass("NSURL")
    NSURLRequest = objc.ObjCClass("NSURLRequest")
    NSMenu = objc.ObjCClass("NSMenu")
    WKWebView = objc.ObjCClass("WKWebView")
    WKWebViewConfiguration = objc.ObjCClass("WKWebViewConfiguration")

    # 进程名与 Dock 图标：进程实际是内置 Python，这里改成应用自己的名字和图标
    try:
        objc.ObjCClass("NSProcessInfo").processInfo.setProcessName_("QSB Studio")
    except Exception:  # noqa: BLE001
        log.debug("设置进程名失败", exc_info=True)
    try:
        info = objc.ObjCClass("NSBundle").mainBundle.infoDictionary
        if info is not None:
            objc.send_message(info, "setObject:forKey:", objc.ns_from_py("QSB Studio"),
                              objc.ns_from_py("CFBundleName"), restype=None,
                              argtypes=[objc.objc_id, objc.objc_id])
    except Exception:  # noqa: BLE001
        log.debug("设置菜单栏应用名失败", exc_info=True)

    app = NSApplication.sharedApplication
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    icon = os.path.abspath(os.path.join(base, "..", "AppIcon.icns"))
    if os.path.exists(icon):
        try:
            app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(icon))
        except Exception:  # noqa: BLE001
            log.debug("设置 Dock 图标失败", exc_info=True)

    class QSBAppDelegate(NSObject):
        @objc_method
        def applicationShouldTerminateAfterLastWindowClosed_(self, sender) -> bool:
            return True

    delegate = QSBAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    log_path = os.path.expanduser("~/Library/Application Support/QSB Studio/qsb-studio.log")

    class QSBNavDelegate(NSObject):
        """页面加载失败时显示说明，而不是留下一个空白窗口。"""
        @objc_method
        def webView_didFailProvisionalNavigation_withError_(self, webview, navigation, error) -> None:
            log.error("页面加载失败：%s", error)
            webview.loadHTMLString_baseURL_(
                "<html><body style='font:15px -apple-system;margin:15vh auto;max-width:520px;line-height:1.7'>"
                "<h2>QSB Studio 页面加载失败</h2><p>内置服务没有响应。请关闭窗口后重新打开；"
                f"若仍失败，请把日志文件发给开发者：<br><code>{log_path}</code></p></body></html>", None)

    nav_delegate = QSBNavDelegate.alloc().init()

    # 菜单：Edit 菜单必不可少——没有它，网页输入框里的 ⌘C / ⌘V / ⌘A 不起作用
    cmd, shift = NSEventModifierFlagCommand, NSEventModifierFlagCommand | NSEventModifierFlagShift
    menubar = NSMenu.alloc().init()
    menubar.addItem_(_menu(objc, "QSB Studio", [
        ("关于 QSB Studio", "orderFrontStandardAboutPanel:", "", None), None,
        ("隐藏 QSB Studio", "hide:", "h", None),
        ("隐藏其他", "hideOtherApplications:", "h", NSEventModifierFlagCommand | NSEventModifierFlagOption),
        ("全部显示", "unhideAllApplications:", "", None), None,
        ("退出 QSB Studio", "terminate:", "q", None)]))
    menubar.addItem_(_menu(objc, "编辑", [
        ("撤销", "undo:", "z", None), ("重做", "redo:", "z", shift), None,
        ("剪切", "cut:", "x", None), ("拷贝", "copy:", "c", None), ("粘贴", "paste:", "v", None),
        ("全选", "selectAll:", "a", None)]))
    menubar.addItem_(_menu(objc, "显示", [
        ("进入全屏幕", "toggleFullScreen:", "f", NSEventModifierFlagCommand | NSEventModifierFlagControl)]))
    menubar.addItem_(_menu(objc, "窗口", [
        ("最小化", "performMiniaturize:", "m", None), ("缩放", "performZoom:", "", None), None,
        ("关闭窗口", "performClose:", "w", None)]))
    app.setMainMenu_(menubar)

    style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
             NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 1360, 880), style, NSBackingStoreBuffered, False)
    win.setTitle_("QSB Studio")
    win.setMinSize_(NSMakeSize(1000, 660))
    win.setReleasedWhenClosed_(False)
    win.center()
    win.setFrameAutosaveName_("QSBStudioMainWindow")   # 记住上次的大小与位置

    cfg = WKWebViewConfiguration.alloc().init()
    web = WKWebView.alloc().initWithFrame_configuration_(win.contentView.bounds, cfg)
    web.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    web.setNavigationDelegate_(nav_delegate)
    win.contentView.addSubview_(web)
    web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(url)))

    # 供 /api/quit 等后台线程安全地结束程序（state 即 app.py 的 State，由调用方传入）
    state.on_quit = lambda: app.performSelectorOnMainThread_withObject_waitUntilDone_(
        objc.SEL("terminate:"), None, False)

    win.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    log.info("原生窗口已打开（WKWebView）：%s", url)
    _keep = (delegate, nav_delegate, win, web, cfg, menubar)   # noqa: F841 — 保持 Python 端引用
    app.run()
