#!/usr/bin/env python3
import subprocess
import os
import re
import sys

class Analyzer:
    # Parses readelf -d output for NEEDED shared libraries
    _READELF_RE = re.compile(r'\(NEEDED\)\s+Shared library:\s+\[(.*?)\]')

    def analyze_source(self, project_path):
        if not os.path.isdir(project_path):
            print(f"[ERROR] Target project directory '{project_path}' does not exist.")
            return False
        return True

    def analyze_binary_deps(self, binary_paths):
        all_so_files = set()
        for b_path in binary_paths:
            so_files = self._run_readelf(b_path)
            all_so_files.update(so_files)
        
        return self._map_to_packages(list(all_so_files))

    def _run_readelf(self, binary_path):
        """Statically analyzes an ELF binary (cross-architecture safe)"""
        print(f"    Static Analysis (readelf): {binary_path}")
        try:
            result = subprocess.run(['readelf', '-d', binary_path], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[WARN] readelf failed or file is not a dynamic ELF: {binary_path}")
            return []
        
        so_files = []
        for line in result.stdout.splitlines():
            match = self._READELF_RE.search(line)
            if match:
                so_files.append(match.group(1))
        return so_files

    def _map_to_packages(self, so_files):
        if not so_files:
            return set()
        
        packages = set()
        print(f"    Mapping {len(so_files)} extracted libraries to standard host packages...")
        
        # FIX APPLIED: Removed packages.add("libc6") from this phase to protect target OS.
        
        for so_name in so_files:
            # Skip PF_RING custom compiled libraries
            if "libpfring" in so_name:
                continue
            
            try:
                # Use dpkg -S on the raw filename to find its parent package
                result = subprocess.run(['dpkg', '-S', so_name], capture_output=True, text=True, check=True)
                lines = result.stdout.strip().splitlines()
                
                for line in lines:
                    if "diversion" in line.lower() or "diverted" in line.lower():
                        continue
                    
                    if ':' in line:
                        pkg_part = line.split(':')[0].strip()
                        for pkg in pkg_part.split(','):
                            pkg = pkg.strip().split(':')[0]
                            if pkg:
                                packages.add(pkg)
            except subprocess.CalledProcessError:
                pass
        
        print(f"    [*] Base mapped packages: {packages}")
        return packages