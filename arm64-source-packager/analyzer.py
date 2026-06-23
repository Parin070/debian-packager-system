#!/usr/bin/env python3
import os
import subprocess
import re
import sys

class Analyzer:
    def __init__(self):
        # Regex engines to parse dynamic linkage records natively
        self._LDD_LINE_RE = re.compile(r'^\s*(\S+)\s+=>\s+(\S+)\s+\(0x[0-9a-fA-F]+\)')
        self._LDD_DIRECT_RE = re.compile(r'^\s*(/\S+)\s+\(0x[0-9a-fA-F]+\)')
        self._SKIP_NAMES = frozenset(['linux-vdso.so.1', 'linux-gate.so.1'])

    def analyze_source(self, project_path):
        """Verifies that the source folder exists cleanly."""
        print(f"[*] Analyzing target project path: {project_path}")
        if not os.path.isdir(project_path):
            print(f"[-] Error: Target directory '{project_path}' does not exist.")
            return False
        return True

    def analyze_binary_deps(self, binary_path):
        """Discovers shared library paths via ldd and maps them to package names via dpkg -S."""
        print(f"[*] Running dependency analysis on binary: {binary_path}")
        
        # 1. Invoke system ldd execution to trace shared object linkages
        try:
            result = subprocess.run(['ldd', binary_path], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if 'not a dynamic executable' in (e.stderr or '') or 'not a dynamic executable' in (e.stdout or ''):
                print("    [INFO] Static binary detected. No shared library deps.")
                return set()
            print(f"[ERROR] ldd failed: {e.stderr.strip()}")
            sys.exit(1)

        so_files = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if any(skip in line for skip in self._SKIP_NAMES):
                continue
            match = self._LDD_LINE_RE.match(line)
            if match:
                resolved_path = match.group(2)
                if resolved_path and resolved_path != 'not' and not resolved_path.startswith('('):
                    so_files.append(resolved_path)
                continue
            match = self._LDD_DIRECT_RE.match(line)
            if match:
                so_files.append(match.group(1))

        # 2. Iteratively map resolved .so paths to tracking packages via dpkg -S
        packages = set()
        if so_files:
            print(f"    Mapping {len(so_files)} shared libraries to tracking packages...")
            for so_path in so_files:
                try:
                    res = subprocess.run(['dpkg', '-S', so_path], capture_output=True, text=True, check=True)
                    for line in res.stdout.strip().splitlines():
                        if ':' in line:
                            pkg_part = line.split(':')[0].strip()
                            for pkg in pkg_part.split(','):
                                pkg = pkg.strip().split(':')[0] # Remove architecture markers
                                if pkg:
                                    packages.add(pkg)
                except subprocess.CalledProcessError:
                    continue
        return packages