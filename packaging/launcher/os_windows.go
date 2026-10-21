//go:build windows

package main

import (
	"os/exec"
	"syscall"
	"unsafe"
)

const createNoWindow = 0x08000000

func hideWindow(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
}

func fail(msg string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	box := user32.NewProc("MessageBoxW")
	title, _ := syscall.UTF16PtrFromString("QSB Studio")
	text, _ := syscall.UTF16PtrFromString(msg)
	const mbIconError = 0x10
	box.Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), mbIconError)
}
