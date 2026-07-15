#!/usr/bin/env python3
"""
airgap-packager: CLI tool to package a binary and all its dependencies
into a single .deb for air-gapped deployment.
"""

import argparse
import os
import sys
import shutil
import subprocess
import re
import json
from analyzer import Analyzer
from resolver import Resolver
from downloader import Downloader
from builder import Builder


def is_elf_binary(path):
    """Check if a file is an ELF binary by reading magic bytes."""
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
        return magic == b'\x7fELF'
    except (IOError, PermissionError):
        return False


def resolve_real_binary(path):
    """
    If the given path is a shell wrapper (not ELF), search standard
    locations for the real ELF binary. Returns the resolved path or
    exits with an error.
    """
    if is_elf_binary(path):
        return path

    name = os.path.basename(path)
    print(f"    [INFO] {path} is not an ELF binary (likely a shell wrapper)")
    print(f"    [INFO] Searching for real ELF binary for '{name}'...")

    search_paths = [
        f'/usr/lib/{name}/{name}',
        f'/usr/lib/x86_64-linux-gnu/{name}',
        f'/usr/libexec/{name}',
    ]

    for candidate in search_paths:
        if os.path.isfile(candidate) and is_elf_binary(candidate):
            print(f"    [INFO] Found real binary: {candidate}")
            return candidate

    print(f"[ERROR] Path is a shell wrapper, not an ELF binary. Find the real binary.")
    print(f"    Checked:")
    for p in search_paths:
        print(f"      - {p}")
    sys.exit(1)


def find_binaries_in_project(project_path):
    """Find all executable ELF binaries inside a project directory."""
    # Look for common binary locations
    candidates = []
    for root, dirs, files in os.walk(project_path):
        # Skip hidden directories and common non-binary dirs
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            fpath = os.path.join(root, f)
            if os.access(fpath, os.X_OK) and not f.endswith(('.py', '.sh', '.md', '.txt', '.cfg', '.ini')):
                # Check if it's an ELF binary
                try:
                    with open(fpath, 'rb') as fp:
                        magic = fp.read(4)
                    if magic == b'\x7fELF':
                        candidates.append(fpath)
                except (IOError, PermissionError):
                    continue

    if not candidates:
        print(f"[ERROR] No ELF binary found in project directory: {project_path}")
        sys.exit(1)

    return candidates


def get_package_binary(package_name):
    """Get the main binary associated with an installed debian package."""
    try:
        result = subprocess.run(
            ['dpkg', '-L', package_name],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError:
        print(f"[ERROR] Package '{package_name}' is not installed.")
        sys.exit(1)

    # Look for executables in standard bin paths
    bin_dirs = ['/usr/bin/', '/usr/sbin/', '/usr/local/bin/', '/bin/', '/sbin/']
    binaries = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if any(line.startswith(d) for d in bin_dirs) and os.path.isfile(line):
            if os.access(line, os.X_OK):
                binaries.append(line)

    if not binaries:
        print(f"[ERROR] No executable binary found for package '{package_name}'.")
        sys.exit(1)

    # Prefer the one whose name matches the package
    for b in binaries:
        if os.path.basename(b) == package_name:
            return b

    return binaries[0]


def main():
    parser = argparse.ArgumentParser(
        prog='airgap-packager',
        description='Package a binary with all dependencies into a single .deb for air-gapped deployment.',
        epilog='Example: %(prog)s --binary /usr/bin/curl -o curl-airgap.deb'
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--binary', metavar='PATH',
        help='Path to a dynamically linked ELF binary'
    )
    input_group.add_argument(
        '--project', metavar='PATH',
        help='Path to a project directory containing a main binary'
    )
    input_group.add_argument(
        '--package', metavar='NAME',
        help='Name of an already-installed Debian package'
    )

    parser.add_argument(
        '-o', '--output', metavar='PATH',
        help='Output .deb file path (default: <name>-airgap.deb)'
    )
    parser.add_argument(
        '-n', '--name', metavar='NAME',
        help='Package name for the output .deb (default: derived from binary name)'
    )
    parser.add_argument(
        '-v', '--version', metavar='VER', default='1.0.0',
        help='Version string for the output .deb (default: 1.0.0)'
    )
    parser.add_argument(
        '--description', metavar='DESC',
        help='Description for the output .deb'
    )


    args = parser.parse_args()

    # ── Step 1: Detect input type and resolve binary path ──
    print("=" * 60)
    print("  airgap-packager")
    print("=" * 60)

    binary_paths = []
    extra_payload_files = []

    if args.binary:
        binary_path = os.path.abspath(args.binary)
        if not os.path.isfile(binary_path):
            print(f"[ERROR] Binary not found: {binary_path}")
            sys.exit(1)
        print(f"[*] Input type: binary")
        print(f"    Path: {binary_path}")
        binary_paths = [resolve_real_binary(binary_path)]

    elif args.project:
        project_path = os.path.abspath(args.project)
        if not os.path.isdir(project_path):
            print(f"[ERROR] Project directory not found: {project_path}")
            sys.exit(1)
        print(f"[*] Input type: project directory")
        print(f"    Path: {project_path}")
        binary_paths = find_binaries_in_project(project_path)
        print(f"    Detected {len(binary_paths)} binaries")
        for b in binary_paths:
            print(f"      - {b}")

    elif args.package:
        print(f"[*] Input type: installed package")
        print(f"    Package: {args.package}")
        binary_paths = [get_package_binary(args.package)]
        print(f"    Detected binary: {binary_paths[0]}")

    config = {}
    if args.project:
        manifest_path = os.path.join(project_path, 'packager.json')
        if os.path.isfile(manifest_path):
            with open(manifest_path, 'r') as f:
                config = json.load(f)
            print(f"[*] Loaded package manifest: {manifest_path}")

    # Derive package name
    if args.name:
        pkg_name = args.name
    elif args.project:
        pkg_name = os.path.basename(os.path.abspath(args.project))
    else:
        pkg_name = os.path.basename(binary_paths[0])
    pkg_name = re.sub(r'[^a-z0-9\-\+\.]', '-', pkg_name.lower())
    output_path = args.output or f"{pkg_name}-airgap.deb"
    staging_dir = f'/tmp/airgap-staging-{pkg_name}'
    description = args.description or f"Air-gapped package for {pkg_name}"

    print(f"\n[*] Package name : {pkg_name}")
    print(f"[*] Version      : {args.version}")
    print(f"[*] Output       : {output_path}")
    print(f"[*] Staging dir  : {staging_dir}")
    print()

    # ── Step 2: Analyze binary ──
    print("-" * 60)
    print("[Step 1/5] Analyzing binary dependencies (ldd + dpkg -S)")
    print("-" * 60)
    analyzer = Analyzer()
    so_files, dep_packages = analyzer.analyze(binary_paths)
    print(f"    Found {len(so_files)} shared libraries")
    print(f"    Mapped to {len(dep_packages)} packages")
    for pkg in sorted(dep_packages):
        print(f"      - {pkg}")
    print()

    # ── Step 3: Resolve full dependency tree ──
    print("-" * 60)
    print("[Step 2/5] Resolving full dependency tree (apt-cache depends)")
    print("-" * 60)
    resolver = Resolver()
    all_deps = resolver.resolve(dep_packages)
    print(f"    Total packages after recursive resolution: {len(all_deps)}")
    print()

    # ── Step 4: Download all .deb files ──
    print("-" * 60)
    print("[Step 3/5] Downloading .deb files (apt-get download)")
    print("-" * 60)
    downloader = Downloader(staging_dir)
    downloader.download(all_deps)
    print()

    # ── Step 5: Copy payload ──
    print("-" * 60)
    print("[Step 4/5] Preparing payload")
    print("-" * 60)
    payload_dir = os.path.join(staging_dir, 'payload')
    install_mode = config.get('install_mode', 'flat')
    if install_mode == 'structured' and args.project:
        payload_source = config.get('payload_source', project_path)
        if os.path.exists(payload_dir):
            shutil.rmtree(payload_dir)
        shutil.copytree(payload_source, payload_dir, ignore=shutil.ignore_patterns('.git', 'packager.json'))
        print(f"    Copied structured payload from {payload_source} -> {payload_dir}")
    else:
        os.makedirs(payload_dir, exist_ok=True)
        for b_path in binary_paths:
            dest = os.path.join(payload_dir, os.path.basename(b_path))
            shutil.copy2(b_path, dest)
            os.chmod(dest, 0o755)
            print(f"    Copied {b_path} -> {dest}")
    print()

    # ── Step 6: Build .deb ──
    print("-" * 60)
    print("[Step 5/5] Building .deb package")
    print("-" * 60)
    builder = Builder(staging_dir)
    builder.build(
        pkg_name=pkg_name,
        version=args.version,
        description=description,
        output_path=output_path,
        config=config
    )
    print()

    # ── Done ──
    print("=" * 60)
    final_size = os.path.getsize(output_path)
    print(f"[SUCCESS] Built: {output_path} ({final_size / 1024 / 1024:.1f} MB)")
    print("=" * 60)
    print()
    print("To install on the air-gapped target:")
    print(f"  sudo dpkg -i {output_path}")
    print()


if __name__ == '__main__':
    main()
