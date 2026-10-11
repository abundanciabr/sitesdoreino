#!/usr/bin/env python3
"""Saída exclusiva para o pipe de credenciais do Git; não usar no terminal."""
import os
import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(1)
    if "Username" in sys.argv[1]:
        print("x-access-token")
    elif "Password" in sys.argv[1] and "github.com" in sys.argv[1]:
        print(os.environ["GITHUB_TOKEN"])
    else:
        raise SystemExit(1)
