#!/usr/bin/env python3
"""
analyzer.py — Runs ldd on a binary to discover shared library dependencies,
then maps each .so file to its owning Debian package via dpkg -S.
"""

import subprocess
import re
import sys


class Analyzer:
    """Analyze a binary's shared library dependencies and map them to packages."""

    # Regex to parse ldd output lines like:
    #   libfoo.so.1 => /usr/lib/x86_64-linux-gnu/libfoo.so.1 (0x00007f...)
    #   /lib64/ld-linux-x86-64.so.2 (0x00007f...)
    _LDD_LINE_RE = re.compile(
        r'^\s*(\S+)\s+=>\s+(\S+)\s+\(0x[0-9a-fA-F]+\)',
    )
    _LDD_DIRECT_RE = re.compile(
        r'^\s*(/\S+)\s+\(0x[0-9a-fA-F]+\)',
    )

    # Virtual packages and pseudo-entries to skip
    _SKIP_NAMES = frozenset([
        'linux-vdso.so.1',
        'linux-gate.so.1',
    ])

    def analyze(self, binary_path):
        """
        Analyze a binary and return (so_files, packages).

        Args:
            binary_path: Absolute path to the ELF binary.

        Returns:
            so_files:  list of resolved .so file paths
            packages:  set of Debian package names that own those .so files
        """
        so_files = self._run_ldd(binary_path)
        packages = self._map_to_packages(so_files)
        return so_files, packages

    def _run_ldd(self, binary_path):
        """Run ldd on the binary and parse shared library paths."""
        print(f"    Running: ldd {binary_path}")
        try:
            result = subprocess.run(
                ['ldd', binary_path],
                capture_output=True, text=True, check=True
            )
        except FileNotFoundError:
            print("[ERROR] 'ldd' not found. This tool requires a Debian/Ubuntu system.")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            if 'not a dynamic executable' in (e.stderr or '') or \
               'not a dynamic executable' in (e.stdout or ''):
                print("    [INFO] Static binary detected. No shared library deps.")
                return []
            print(f"[ERROR] ldd failed: {e.stderr.strip()}")
            sys.exit(1)

        so_files = []
        for line in result.stdout.splitlines():
            line = line.strip()

            # Skip virtual/kernel-provided DSOs
            if any(skip in line for skip in self._SKIP_NAMES):
                continue

            # Match "libname.so => /path/to/libname.so (0x...)"
            match = self._LDD_LINE_RE.match(line)
            if match:
                resolved_path = match.group(2)
                if resolved_path and resolved_path != 'not' and not resolved_path.startswith('('):
                    so_files.append(resolved_path)
                continue

            # Match standalone "/path/to/ld-linux.so (0x...)"
            match = self._LDD_DIRECT_RE.match(line)
            if match:
                so_files.append(match.group(1))

        return so_files

    def _map_to_packages(self, so_files):
        """Map shared library paths to owning Debian packages via dpkg -S."""
        if not so_files:
            return set()

        packages = set()
        # Batch query — dpkg -S can take multiple paths
        # But it may fail if any single path is not owned; fall back to one-by-one
        print(f"    Running: dpkg -S on {len(so_files)} libraries")

        for so_path in so_files:
            try:
                result = subprocess.run(
                    ['dpkg', '-S', so_path],
                    capture_output=True, text=True, check=True
                )
                for line in result.stdout.strip().splitlines():
                    # Output format: "package-name:arch: /path/to/file"
                    if ':' in line:
                        pkg_part = line.split(':')[0].strip()
                        # Handle multi-arch package names (e.g. "libc6:amd64")
                        # dpkg -S may return "pkg:arch: path" or "pkg, pkg2: path"
                        for pkg in pkg_part.split(','):
                            pkg = pkg.strip()
                            if pkg:
                                packages.add(pkg)
            except subprocess.CalledProcessError:
                # Not owned by any package (could be locally compiled)
                print(f"    [WARN] No package owns: {so_path}")

        # Filter out architecture qualifiers — we want just package names
        clean_packages = set()
        for pkg in packages:
            # Remove :amd64, :i386, etc.
            base = pkg.split(':')[0] if ':' in pkg else pkg
            clean_packages.add(base)

        return clean_packages
