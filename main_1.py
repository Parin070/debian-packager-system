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
    print("        Universal Airgap Packager Wizard")
    print("=" * 60)
    print()

    print("Target architecture:")
    print("  [1] amd64  — x86_64 (standard desktop/server)")
    print("  [2] arm64  — aarch64 (Raspberry Pi, ARM servers, Edge nodes)")
    print()
    arch = prompt("Select [1/2]: ", options=['1', '2'])
    print()

    if arch == '1':
        _run_amd64()
    else:
        _run_arm64()


def _run_amd64():
    # Leaving the AMD64 flow completely untouched as requested
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

    print("Input pathway configuration type:")
    print("  [1] Binary/Directory — path to an ELF binary or a folder of compiled tools")
    print("  [2] Project Source   — path to a Python project layout folder")
    print("  [3] Debian Package   — name of an installed system package to mirror")
    print()
    choice = prompt("Select Input Type [1/2/3]: ", options=['1', '2', '3'])
    print()

    # Collect custom naming and description metadata
    name = prompt("Package name (e.g., pfring-suite): ")
    version = input("Version [default: 1.0.0]: ").strip() or '1.0.0'
    description = input("Description [default: Universal ARM64 offline bundle]: ").strip() or 'Universal ARM64 offline bundle'
    print()

    args = [sys.executable, ARM64_MAIN]

    if choice == '1':
        path_input = prompt("Enter path to compiled binary or framework tools folder: ")
        # Safely expand the '~' to the full home directory path
        abs_path = os.path.abspath(os.path.expanduser(path_input))
        args += ['--binary', abs_path]

    elif choice == '2':
        path_input = prompt("Python project directory path: ")
        # Safely expand the '~' for Python projects too
        abs_path = os.path.abspath(os.path.expanduser(path_input))
        args += ['--path', abs_path]

    elif choice == '3':
        pkg_input = prompt("Target package name: ")
        args += ['--package', pkg_input]
    
    # Append the metadata arguments
    args += [
        '--name', name,
        '--version', version,
        '--description', description,
    ]

    print("[*] Launching underlying core cross-architecture build engines...")
    subprocess.run(args)


if __name__ == '__main__':
    main()