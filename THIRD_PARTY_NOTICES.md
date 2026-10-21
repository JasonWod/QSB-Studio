# 第三方组件声明

QSB Studio 本身以 MIT 许可证发布。打包后的应用包含以下第三方组件，均允许随应用再分发：

| 组件 | 用途 | 许可证 | 来源 |
|---|---|---|---|
| CPython 3.12（python-build-standalone 构建） | Windows / macOS 应用内置的 Python 运行时 | Python Software Foundation License（及其附带组件的许可证，见运行时目录中的 LICENSE.txt） | https://github.com/astral-sh/python-build-standalone |
| go-webview2 | Windows 原生窗口（WebView2） | MIT | https://github.com/jchv/go-webview2 |
| go-winloader | 在内存中加载 WebView2Loader | MIT | https://github.com/jchv/go-winloader |
| WebView2Loader.dll | 微软 WebView2 SDK 加载器（内嵌于 Windows 启动器） | Microsoft WebView2 SDK License（允许随应用分发） | https://developer.microsoft.com/microsoft-edge/webview2/ |
| golang.org/x/sys（windows 包） | Windows 系统调用 | BSD-3-Clause | https://github.com/golang/sys |
| rubicon-objc 0.5.7 | macOS 原生窗口（通过 ctypes 调用 Objective-C） | BSD-3-Clause | https://github.com/beeware/rubicon-objc |

各组件的完整许可证文本随源码保存在 `packaging/launcher/third_party/*/LICENSE*`、`vendor/rubicon/LICENSE`。

运行环境：Windows 版使用系统自带的 Microsoft Edge WebView2 运行时（Windows 11 及更新过的 Windows 10 均已内置）；
macOS 版使用系统自带的 WebKit。两者都是操作系统组件，无需另行安装。
