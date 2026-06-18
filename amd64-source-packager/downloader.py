#!/usr/bin/env python3
"""
downloader.py — Downloads .deb files for a set of packages
using apt-get download into a staging directory.
"""

import os
import subprocess
import sys


class Downloader:
    """Download .deb files for all resolved packages into a staging area."""

    def __init__(self, staging_dir):
        """
        Args:
            staging_dir: Root staging directory path.
        """
        self.staging_dir = staging_dir
        self.deps_dir = os.path.join(staging_dir, 'deps')

    def download(self, packages):
        """
        Download .deb files for all given package names.

        Args:
            packages: set/list of package name strings
        """
        os.makedirs(self.deps_dir, exist_ok=True)

        pkg_list = sorted(packages)
        total = len(pkg_list)
        success = 0
        failed = []

        print(f"    Downloading {total} packages into {self.deps_dir}")

        for i, pkg in enumerate(pkg_list, 1):
            status = self._download_one(pkg, i, total)
            if status:
                success += 1
            else:
                failed.append(pkg)

        print(f"    Downloaded: {success}/{total}")
        if failed:
            print(f"    [WARN] Failed to download {len(failed)} packages:")
            for pkg in failed:
                print(f"      - {pkg}")

    def _download_one(self, package_name, index, total):
        """
        Download a single package's .deb file.

        Returns True on success, False on failure.
        """
        progress = f"[{index}/{total}]"
        print(f"    {progress} Downloading: {package_name}", end='', flush=True)

        try:
            result = subprocess.run(
                ['apt-get', 'download', package_name],
                capture_output=True, text=True,
                cwd=self.deps_dir
            )
            if result.returncode == 0:
                print(" ✓")
                return True
            else:
                # Try with apt-cache to get the exact package name
                # Some packages need architecture specified
                print(f" ✗ (retrying with arch...)", end='', flush=True)
                result2 = subprocess.run(
                    ['apt-get', 'download', f'{package_name}:amd64'],
                    capture_output=True, text=True,
                    cwd=self.deps_dir
                )
                if result2.returncode == 0:
                    print(" ✓")
                    return True
                else:
                    print(f" ✗")
                    stderr = result.stderr.strip()
                    if stderr:
                        print(f"           {stderr[:120]}")
                    return False
        except FileNotFoundError:
            print("[ERROR] 'apt-get' not found. This tool requires a Debian/Ubuntu system.")
            sys.exit(1)

    def get_deb_count(self):
        """Return the number of .deb files in the deps directory."""
        if not os.path.isdir(self.deps_dir):
            return 0
        return sum(1 for f in os.listdir(self.deps_dir) if f.endswith('.deb'))
