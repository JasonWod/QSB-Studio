//go:build windows

package main

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"

	webview2 "github.com/jchv/go-webview2"
	"golang.org/x/sys/windows"
)

const createNoWindow = 0x08000000

// 后台服务进程放进 Job 对象：启动器退出（包括崩溃）时系统自动结束它，不会残留进程。
var job windows.Handle

func startInJob(cmd *exec.Cmd) error {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
	if err := cmd.Start(); err != nil {
		return err
	}
	j, err := windows.CreateJobObject(nil, nil)
	if err != nil {
		return nil // 拿不到 Job 也能运行，只是失去自动清理
	}
	info := windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION{
		BasicLimitInformation: windows.JOBOBJECT_BASIC_LIMIT_INFORMATION{LimitFlags: windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE},
	}
	windows.SetInformationJobObject(j, windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&info)), uint32(unsafe.Sizeof(info)))
	if h, err := windows.OpenProcess(windows.PROCESS_SET_QUOTA|windows.PROCESS_TERMINATE, false, uint32(cmd.Process.Pid)); err == nil {
		windows.AssignProcessToJobObject(j, h)
		windows.CloseHandle(h)
	}
	job = j
	return nil
}

const loadingHTML = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#eef1f3;font-family:"Microsoft YaHei UI","Segoe UI",sans-serif;color:#1f2a37}
.c{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
.b{width:44px;height:44px;border-radius:50%;border:4px solid #c9d6d8;border-top-color:#0f6e78;animation:s 1s linear infinite}
@keyframes s{to{transform:rotate(360deg)}} p{margin:0;color:#5b6b78;font-size:14px}
</style></head><body><div class="c"><div class="b"></div><b>QSB Studio</b><p>正在启动…首次运行需要几秒钟解压</p></div></body></html>`

func errorHTML(msg string) string {
	esc := strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;").Replace(msg)
	return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#eef1f3;font-family:"Microsoft YaHei UI","Segoe UI",sans-serif;color:#1f2a37}
.c{max-width:560px;margin:15vh auto;padding:0 24px;line-height:1.7}h2{color:#b42318}code{background:#fff;padding:2px 6px;border-radius:4px}
</style></head><body><div class="c"><h2>QSB Studio 无法启动</h2><p>` + esc + `</p></div></body></html>`
}

func waitPort(portFile string, done <-chan error) (int, error) {
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) {
		select {
		case err := <-done:
			if err == nil {
				err = fmt.Errorf("服务进程已退出")
			}
			return 0, err
		default:
		}
		if b, err := os.ReadFile(portFile); err == nil {
			if p, err := strconv.Atoi(strings.TrimSpace(string(b))); err == nil && p > 0 {
				return p, nil
			}
		}
		time.Sleep(100 * time.Millisecond)
	}
	return 0, fmt.Errorf("等待服务启动超时")
}

// 与 Python 服务写同一个日志文件，便于排查（CI 也据此判断原生窗口是否成功创建）
func logLine(logFile, msg string) {
	f, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer f.Close()
	fmt.Fprintf(f, "%s INFO [launcher] %s\n", time.Now().Format("2006-01-02 15:04:05,000"), msg)
}

func openBrowser(url string) {
	exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

func runApp(dir, logFile string) {
	portFile := filepath.Join(dataRoot(), fmt.Sprintf("port-%d.txt", os.Getpid()))
	os.Remove(portFile)
	defer os.Remove(portFile)
	cmd := exec.Command(pythonPath(dir), "-I", filepath.Join(dir, "app", "app.py"),
		"--embedded", "--port-file", portFile, "--log-file", logFile)
	cmd.Dir = filepath.Join(dir, "app")
	if err := startInJob(cmd); err != nil {
		fail("无法启动内置 Python：" + err.Error())
		return
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()

	w := webview2.NewWithOptions(webview2.WebViewOptions{
		Debug:     false,
		AutoFocus: true,
		DataPath:  filepath.Join(dataRoot(), "WebView2"),
		WindowOptions: webview2.WindowOptions{
			Title: "QSB Studio", Width: 1360, Height: 880, IconId: 1, Center: true,
		},
	})
	if w == nil {
		// 系统缺少 WebView2 运行时（极少数旧版 Windows 10）：退回到默认浏览器
		logLine(logFile, "未能创建 WebView2 窗口，改用默认浏览器打开")
		port, err := waitPort(portFile, done)
		if err != nil {
			fail("QSB Studio 启动失败：" + err.Error() + "\n\n详细信息见日志：\n" + logFile)
			return
		}
		openBrowser(fmt.Sprintf("http://127.0.0.1:%d", port))
		<-done // 浏览器页面关闭后服务会自动退出
		return
	}
	defer w.Destroy()
	logLine(logFile, "WebView2 原生窗口已创建")
	w.SetSize(1024, 680, webview2.HintMin)
	w.SetHtml(loadingHTML)

	var url string
	go func() {
		port, err := waitPort(portFile, done)
		if err != nil {
			msg := "后台服务没有正常启动（" + err.Error() + "）。详细信息见日志：" + logFile
			w.Dispatch(func() { w.SetHtml(errorHTML(msg)) })
			return
		}
		url = fmt.Sprintf("http://127.0.0.1:%d", port)
		w.Dispatch(func() { w.Navigate(url) })
	}()
	w.Run() // 阻塞到窗口关闭

	if url != "" {
		c := http.Client{Timeout: time.Second}
		if req, err := http.NewRequest("POST", url+"/api/quit", nil); err == nil {
			if resp, err := c.Do(req); err == nil {
				resp.Body.Close()
			}
		}
	}
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		cmd.Process.Kill()
	}
}

func fail(msg string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	box := user32.NewProc("MessageBoxW")
	title, _ := syscall.UTF16PtrFromString("QSB Studio")
	text, _ := syscall.UTF16PtrFromString(msg)
	const mbIconError = 0x10
	box.Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), mbIconError)
}
