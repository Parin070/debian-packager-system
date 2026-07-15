#!/usr/bin/env python3
import subprocess
import os
import re
import sys

class Analyzer:
    _LDD_LINE_RE = re.compile(r'^\s*(\S+)\s+=>\s+(\S+)\s+\(0x[0-9a-fA-F]+\)')
    _LDD_DIRECT_RE = re.compile(r'^\s*(/\S+)\s+\(0x[0-9a-fA-F]+\)')
    _SKIP_NAMES = frozenset(['linux-vdso.so.1', 'linux-gate.so.1'])

    def analyze_source(self, project_path):
        if not os.path.isdir(project_path):
            print(f"[ERROR] Target project directory '{project_path}' does not exist.")
            return False
        return True

    def analyze_binary_deps(self, binary_paths):
        all_so_files = set()
        for b_path in binary_paths:
            so_files = self._run_ldd(b_path)
            all_so_files.update(so_files)
        
        return self._map_to_packages(list(all_so_files))

    def _run_ldd(self, binary_path):
        print(f"    Running: ldd {binary_path}")
        try:
            result = subprocess.run(['ldd', binary_path], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if 'not a dynamic executable' in (e.stderr or '') or 'not a dynamic executable' in (e.stdout or ''):
                print("    [INFO] Static binary detected. No shared library dependencies.")
                return []
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
        return so_files

    def _map_to_packages(self, so_files):
        if not so_files:
            return set()
        packages = set()
        print(f"    Mapping {len(so_files)} libraries to tracked packages via dpkg -S...")
        for so_path in so_files:
            try:
                result = subprocess.run(['dpkg', '-S', so_path], capture_output=True, text=True, check=True)
                for line in result.stdout.strip().splitlines():
                    if ':' in line:
                        pkg_part = line.split(':')[0].strip()
                        for pkg in pkg_part.split(','):
                            pkg = pkg.strip().split(':')[0]
                            if pkg:
                                packages.add(pkg)
            except subprocess.CalledProcessError:
                continue
        return packages
