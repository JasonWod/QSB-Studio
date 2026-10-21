// QSB Studio 启动器：把内嵌的「Python 运行时 + 程序」解压到用户数据目录，然后启动应用。
//
// Windows：打开原生 WebView2 窗口（app_windows.go）；其他系统：以浏览器桌面模式启动（app_other.go，
// 仅用于在 Linux 上验证打包流程）。首次运行（或版本更新后）解压一次，解压目录按载荷哈希区分版本，
// 旧版本目录会被顺手清理。
package main

import (
	"archive/zip"
	"bytes"
	_ "embed"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

//go:embed payload.zip
var payload []byte

// 构建时用 -ldflags "-X main.payloadID=<哈希>" 注入
var payloadID = "dev"

func dataRoot() string {
	if runtime.GOOS == "windows" {
		if d := os.Getenv("LOCALAPPDATA"); d != "" {
			return filepath.Join(d, "QSB Studio")
		}
	}
	if d, err := os.UserCacheDir(); err == nil {
		return filepath.Join(d, "QSB Studio")
	}
	return filepath.Join(os.TempDir(), "QSB Studio")
}

func extract(dst string) error {
	zr, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return err
	}
	clean := filepath.Clean(dst) + string(os.PathSeparator)
	for _, f := range zr.File {
		target := filepath.Join(dst, filepath.FromSlash(f.Name))
		if !strings.HasPrefix(target, clean) { // 防止 zip 路径穿越
			return fmt.Errorf("非法路径: %s", f.Name)
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		if f.Mode()&os.ModeSymlink != 0 { // 符号链接（如 bin/python3 -> python3.12）
			link, err := io.ReadAll(rc)
			rc.Close()
			if err != nil {
				return err
			}
			resolved := filepath.Join(filepath.Dir(target), string(link))
			if filepath.IsAbs(string(link)) || !strings.HasPrefix(resolved, clean) {
				return fmt.Errorf("非法链接: %s -> %s", f.Name, link)
			}
			if err := os.Symlink(string(link), target); err != nil {
				return err
			}
			continue
		}
		mode := f.Mode().Perm() | 0o600
		out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
		if err != nil {
			rc.Close()
			return err
		}
		_, err = io.Copy(out, rc)
		rc.Close()
		if cerr := out.Close(); err == nil {
			err = cerr
		}
		if err != nil {
			return err
		}
	}
	return nil
}

func prepare() (string, error) {
	root := dataRoot()
	dir := filepath.Join(root, "app-"+payloadID)
	marker := filepath.Join(dir, ".complete")
	if _, err := os.Stat(marker); err == nil {
		return dir, nil
	}
	if err := os.MkdirAll(root, 0o755); err != nil {
		return "", err
	}
	tmp := fmt.Sprintf("%s.tmp-%d", dir, os.Getpid())
	os.RemoveAll(tmp)
	if err := extract(tmp); err != nil {
		os.RemoveAll(tmp)
		return "", err
	}
	if err := os.WriteFile(filepath.Join(tmp, ".complete"), []byte(payloadID), 0o644); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, dir); err != nil {
		// 另一个实例可能已同时解压完成
		os.RemoveAll(tmp)
		if _, e2 := os.Stat(marker); e2 != nil {
			return "", err
		}
	}
	// 清理旧版本
	if entries, err := os.ReadDir(root); err == nil {
		for _, e := range entries {
			name := e.Name()
			if e.IsDir() && strings.HasPrefix(name, "app-") && name != "app-"+payloadID {
				os.RemoveAll(filepath.Join(root, name))
			}
		}
	}
	return dir, nil
}

func pythonPath(dir string) string {
	if runtime.GOOS == "windows" {
		return filepath.Join(dir, "runtime", "pythonw.exe")
	}
	return filepath.Join(dir, "runtime", "bin", "python3")
}

func main() {
	dir, err := prepare()
	if err != nil {
		fail("首次运行需要把程序解压到：\n" + dataRoot() + "\n\n解压失败：" + err.Error() +
			"\n\n请确认磁盘空间充足、该目录可写，或以普通用户身份重试。")
		return
	}
	runApp(dir, filepath.Join(dataRoot(), "qsb-studio.log"))
}
