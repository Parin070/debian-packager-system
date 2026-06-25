#!/usr/bin/env python3

import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
AMD64_MAIN = os.path.join(ROOT, 'amd64-source-packager', 'main.py')
ARM64_MAIN = os.path.join(ROOT, 'arm64-source-packager', 'main.py')

def prompt(msg, options=None):
    while True:
        val = input(msg).strip()
        if options:
            if val in options:
                return val
            print(f"    [!] Choose from: {', '.join(options)}")
        elif val:
            return val
        else:
            print("    [!] Cannot be empty.")

def main():
    print("=" * 60)
    print("        airgap-packager")
    print("=" * 60)
    print()

    print("Target architecture:")
    print("  [1] amd64  — x86_64 (standard desktop/server)")
    print("  [2] arm64  — aarch64 (Raspberry Pi, ARM servers)")
    print()
    arch = prompt("Select [1/2]: ", options=['1', '2'])
    print()

    if arch == '1':
        _run_amd64()
    else:
        _run_arm64()


def _run_amd64():
    print("── amd64 mode ──")
    print()

    print("Input type:")
    print("  [1] Binary   — path to a compiled ELF binary")
    print("  [2] Project  — path to a project directory")
    print("  [3] Package  — name of an installed Debian package")
    print()
    choice = prompt("Select [1/2/3]: ", options=['1', '2', '3'])
    print()

    output = input("Output filename [leave blank for default]: ").strip()
    print()

    args = [sys.executable, AMD64_MAIN]

    if choice == '1':
        path = prompt("Binary path: ")
        args += ['--binary', path]
    elif choice == '2':
        path = prompt("Project directory path: ")
        args += ['--project', path]
    elif choice == '3':
        pkg = prompt("Package name: ")
        args += ['--package', pkg]

    if output:
        args += ['-o', output]

    print()
    subprocess.run(args)


def _run_arm64():
    print("── arm64 mode ──")
    print()

    path = prompt("Python project directory path: ")
    name = prompt("Package name: ")
    version = input("Version [default: 1.0.0]: ").strip() or '1.0.0'
    description = input("Description [default: Packaged Python app]: ").strip() or 'Packaged Python app'
    print()

    args = [
        sys.executable, ARM64_MAIN,
        '--path', path,
        '--name', name,
        '--version', version,
        '--description', description,
    ]

    print()
    subprocess.run(args)


if __name__ == '__main__':
    main()