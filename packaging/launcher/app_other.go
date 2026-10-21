//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// 非 Windows 平台没有 WebView2：以浏览器桌面模式启动（用于在 Linux 上验证打包与解压流程）。
func runApp(dir, logFile string) {
	cmd := exec.Command(pythonPath(dir), "-I", filepath.Join(dir, "app", "app.py"), "--desktop", "--log-file", logFile)
	cmd.Dir = filepath.Join(dir, "app")
	if err := cmd.Start(); err != nil {
		fail("无法启动内置 Python：" + err.Error())
		return
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case err := <-done:
		if err != nil {
			fail("QSB Studio 启动后意外退出：" + err.Error() + "\n详细信息见日志：" + logFile)
		}
	case <-time.After(4 * time.Second):
	}
}

func fail(msg string) {
	fmt.Fprintln(os.Stderr, "QSB Studio:", msg)
	os.Exit(1)
}
