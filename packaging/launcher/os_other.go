//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
)

func hideWindow(cmd *exec.Cmd) {}

func fail(msg string) {
	fmt.Fprintln(os.Stderr, "QSB Studio:", msg)
	os.Exit(1)
}
