module qsbstudio/launcher

go 1.21

require (
	github.com/jchv/go-webview2 v0.0.0
	github.com/jchv/go-winloader v0.0.0
	golang.org/x/sys v0.30.0
)

// 第三方库源码随仓库保存在 third_party/（只保留用到的包），离线即可构建：
//   go-webview2 MIT  https://github.com/jchv/go-webview2  @ 5659883
//   go-winloader MIT https://github.com/jchv/go-winloader @ c1995be
//   x/sys BSD-3      https://github.com/golang/sys        @ v0.30.0（仅 windows 包）
replace (
	github.com/jchv/go-webview2 => ./third_party/go-webview2
	github.com/jchv/go-winloader => ./third_party/go-winloader
	golang.org/x/sys => ./third_party/sys
)
