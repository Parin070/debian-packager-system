#!/usr/bin/env python3
"""
resolver.py — Recursively resolves the full dependency tree for a set of
Debian packages using apt-cache depends.
"""

import subprocess
import re
import sys


class Resolver:
    """Resolve the full recursive dependency tree for Debian packages."""

    # Regex to parse apt-cache depends output
    # Lines look like:
    #   Depends: libfoo
    #   PreDepends: bar
    #   |Depends: alt-pkg   (alternative, we take the first)
    _DEP_RE = re.compile(
        r'^\s+[\|]?(?:Pre)?Depends:\s+([a-z0-9][a-z0-9\+\-\.]+)',
    )

    # Virtual/meta packages that should not be downloaded
    _SKIP_PACKAGES = frozenset([
        'base-files',
        'dpkg',
        'debconf',
        'install-info',
    ])

    # Patterns for virtual/abstract packages to skip
    _SKIP_PATTERNS = re.compile(
        r'^(?:<.*>)$'  # Virtual packages shown as <name>
    )

    def resolve(self, seed_packages):
        """
        Recursively resolve all dependencies for the given seed packages.

        Args:
            seed_packages: set of package name strings

        Returns:
            set of all package names (including the seeds) needed
        """
        all_deps = set()
        visited = set()
        queue = list(seed_packages)

        print(f"    Seed packages: {len(seed_packages)}")

        while queue:
            pkg = queue.pop(0)

            # Normalize and skip if already visited
            pkg = pkg.strip()
            if not pkg or pkg in visited:
                continue
            if self._SKIP_PATTERNS.match(pkg):
                continue

            visited.add(pkg)
            all_deps.add(pkg)

            # Get dependencies for this package
            deps = self._get_depends(pkg)
            for dep in deps:
                if dep not in visited and dep not in self._SKIP_PACKAGES:
                    queue.append(dep)

        print(f"    Visited {len(visited)} packages during resolution")
        return all_deps

    def _get_depends(self, package_name):
        """
        Run apt-cache depends on a single package and return its direct
        Depends/PreDepends as a set of package names.
        """
        try:
            result = subprocess.run(
                ['apt-cache', 'depends', '--no-recommends',
                 '--no-suggests', '--no-conflicts',
                 '--no-breaks', '--no-replaces',
                 '--no-enhances', package_name],
                capture_output=True, text=True, check=True
            )
        except FileNotFoundError:
            print("[ERROR] 'apt-cache' not found. This tool requires a Debian/Ubuntu system.")
            sys.exit(1)
        except subprocess.CalledProcessError:
            # Package may not exist in apt cache (virtual, transitional, etc.)
            return set()

        deps = set()
        for line in result.stdout.splitlines():
            match = self._DEP_RE.match(line)
            if match:
                dep_name = match.group(1).strip()
                # Skip virtual package placeholders
                if dep_name.startswith('<') and dep_name.endswith('>'):
                    continue
                # Strip architecture qualifier
                if ':' in dep_name:
                    dep_name = dep_name.split(':')[0]
                deps.add(dep_name)

        return deps
