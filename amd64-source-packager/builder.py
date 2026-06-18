#!/usr/bin/env python3
"""
builder.py — Assembles the staging directory into a proper Debian package
structure and builds the final .deb using dpkg-deb --build.
"""

import os
import shutil
import stat
import subprocess
import sys


TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


class Builder:
    """Assemble staging files and build the final .deb package."""

    def __init__(self, staging_dir):
        """
        Args:
            staging_dir: Root staging directory containing deps/ and payload/.
        """
        self.staging_dir = staging_dir
        self.deps_dir = os.path.join(staging_dir, 'deps')
        self.payload_dir = os.path.join(staging_dir, 'payload')

    def build(self, pkg_name, version, description, binary_name, output_path):
        """
        Build the final .deb package.

        Args:
            pkg_name:    Package name for the .deb
            version:     Version string
            description: Package description
            binary_name: Name of the main binary file
            output_path: Where to write the final .deb
        """
        build_root = os.path.join(self.staging_dir, 'build')

        # Clean previous build
        if os.path.exists(build_root):
            shutil.rmtree(build_root)

        # Create directory structure inside the .deb
        #   /opt/airgap/deps/    — all dependency .deb files
        #   /opt/airgap/payload/ — the main binary
        #   DEBIAN/control       — package metadata
        #   DEBIAN/postinst      — post-install script
        opt_deps = os.path.join(build_root, 'opt', 'airgap', pkg_name, 'deps')
        opt_payload = os.path.join(build_root, 'opt', 'airgap', pkg_name, 'payload')
        debian_dir = os.path.join(build_root, 'DEBIAN')

        os.makedirs(opt_deps, exist_ok=True)
        os.makedirs(opt_payload, exist_ok=True)
        os.makedirs(debian_dir, exist_ok=True)

        # Copy dependency .deb files
        deb_count = 0
        if os.path.isdir(self.deps_dir):
            for f in os.listdir(self.deps_dir):
                if f.endswith('.deb'):
                    src = os.path.join(self.deps_dir, f)
                    dst = os.path.join(opt_deps, f)
                    shutil.copy2(src, dst)
                    deb_count += 1
        print(f"    Packed {deb_count} dependency .deb files")

        # Copy payload binary
        payload_count = 0
        if os.path.isdir(self.payload_dir):
            for f in os.listdir(self.payload_dir):
                src = os.path.join(self.payload_dir, f)
                dst = os.path.join(opt_payload, f)
                shutil.copy2(src, dst)
                os.chmod(dst, 0o755)
                payload_count += 1
        print(f"    Packed {payload_count} payload file(s)")

        # Calculate installed size (in KB)
        installed_size = self._dir_size_kb(build_root)

        # Write DEBIAN/control from template
        self._write_control(
            debian_dir, pkg_name, version, description, installed_size
        )
        print(f"    Wrote DEBIAN/control")

        # Write DEBIAN/postinst from template
        self._write_postinst(debian_dir, binary_name)
        print(f"    Wrote DEBIAN/postinst")

        # Build .deb
        output_path = os.path.abspath(output_path)
        print(f"    Running: dpkg-deb --build {build_root} {output_path}")
        try:
            result = subprocess.run(
                ['dpkg-deb', '--build', build_root, output_path],
                capture_output=True, text=True, check=True
            )
            print(f"    {result.stdout.strip()}")
        except FileNotFoundError:
            print("[ERROR] 'dpkg-deb' not found. This tool requires a Debian/Ubuntu system.")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] dpkg-deb failed: {e.stderr.strip()}")
            sys.exit(1)

    def _write_control(self, debian_dir, pkg_name, version, description, installed_size):
        """Render the control file template and write it."""
        template_path = os.path.join(TEMPLATES_DIR, 'control')
        with open(template_path, 'r') as f:
            template = f.read()

        content = template.format(
            package=pkg_name,
            version=version,
            installed_size=installed_size,
            description=description,
        )

        control_path = os.path.join(debian_dir, 'control')
        with open(control_path, 'w', newline='\n') as f:
            f.write(content)

    def _write_postinst(self, debian_dir, binary_name):
        """Render the postinst script template and write it."""
        template_path = os.path.join(TEMPLATES_DIR, 'postinst')
        with open(template_path, 'r') as f:
            template = f.read()

        content = template.format(
            binary_name=binary_name,
        )

        postinst_path = os.path.join(debian_dir, 'postinst')
        with open(postinst_path, 'w', newline='\n') as f:
            f.write(content)
        # postinst must be executable
        os.chmod(postinst_path, 0o755)

    @staticmethod
    def _dir_size_kb(path):
        """Calculate total size of a directory tree in kilobytes."""
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total // 1024
