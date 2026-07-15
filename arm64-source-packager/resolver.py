#!/usr/bin/env python3
import subprocess
import re
import sys

class Resolver:
    _DEP_RE = re.compile(r'^\s+[\|]?(?:Pre)?Depends:\s+([a-z0-9][a-z0-9\+\-\.]+)')
    _SKIP_PACKAGES = frozenset(['base-files', 'dpkg', 'debconf', 'install-info'])
    _SKIP_PATTERNS = re.compile(r'^(?:<.*>)$')

    def resolve(self, seed_packages):
        all_deps = set()
        visited = set()
        queue = list(seed_packages)

        print(f"    Seed packages for tree resolution: {len(seed_packages)}")
        while queue:
            pkg = queue.pop(0).strip()
            if not pkg or pkg in visited or self._SKIP_PATTERNS.match(pkg):
                continue

            visited.add(pkg)
            all_deps.add(pkg)

            deps = self._get_depends(pkg)
            for dep in deps:
                if dep not in visited and dep not in self._SKIP_PACKAGES:
                    queue.append(dep)

        print(f"    Total recursive packages mapped: {len(all_deps)}")
        return all_deps

    def _get_depends(self, package_name):
        try:
            result = subprocess.run(
                ['apt-cache', 'depends', '--no-recommends', '--no-suggests', 
                 '--no-conflicts', '--no-breaks', '--no-replaces', package_name],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError:
            return set()
        
        deps = set()
        for line in result.stdout.splitlines():
            match = self._DEP_RE.match(line)
            if match:
                dep_name = match.group(1).strip()
                if dep_name.startswith('<') and dep_name.endswith('>'):
                    continue
                if ':' in dep_name:
                    dep_name = dep_name.split(':')[0]
                deps.add(dep_name)
        return deps