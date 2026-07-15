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

    def build(self, pkg_name, version, description, output_path, config=None):
        """
        Build the final .deb package.

        Args:
            pkg_name:    Package name for the .deb
            version:     Version string
            description: Package description
            output_path: Where to write the final .deb
            config:      Package configuration dict (optional)
        """
        if config is None:
            config = {}
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
            if config.get('install_mode', 'flat') == 'structured':
                shutil.copytree(self.payload_dir, opt_payload, dirs_exist_ok=True)
                for root, _, files in os.walk(self.payload_dir):
                    payload_count += len(files)
            else:
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
        self._write_postinst(debian_dir, pkg_name, config)
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

    def _write_postinst(self, debian_dir, pkg_name, config):
        """Render the postinst script template and write it."""
        template_path = os.path.join(TEMPLATES_DIR, 'postinst')
        with open(template_path, 'r') as f:
            template = f.read()

        install_mode = config.get('install_mode', 'flat')
        install_prefix = config.get('install_prefix', '/usr/local/bin')

        if install_mode == 'structured':
            payload_install_snippet = f"""echo "[*] Installing structured payload to {install_prefix}..."
if [ -d "$PAYLOAD_DIR" ] && [ "$(ls -A "$PAYLOAD_DIR")" ]; then
    mkdir -p "{install_prefix}"
    cp -r "$PAYLOAD_DIR"/* "{install_prefix}/"
    echo "    Installed structured payload to {install_prefix}"
else
    echo "    [WARN] Payload directory not found or empty: $PAYLOAD_DIR"
fi"""
        else:
            payload_install_snippet = """echo "[*] Installing payload binaries..."
if [ -d "$PAYLOAD_DIR" ] && [ "$(ls -A "$PAYLOAD_DIR")" ]; then
    for f in "$PAYLOAD_DIR"/*; do
        if [ -f "$f" ]; then
            bname=$(basename "$f")
            cp "$f" "/usr/local/bin/$bname"
            chmod 755 "/usr/local/bin/$bname"
            echo "    Installed: /usr/local/bin/$bname"
        fi
    done
else
    echo "    [WARN] Payload directory not found or empty: $PAYLOAD_DIR"
fi"""

        kernel_module_snippet = ""
        kernel_module = config.get('kernel_module')
        if kernel_module:
            kernel_module_snippet = f"""
echo "[*] Loading kernel module {kernel_module}..."
MOD_PATH="{install_prefix}/{kernel_module}"
if [ -f "$MOD_PATH" ]; then
    insmod "$MOD_PATH" || modprobe "$(basename "{kernel_module}" .ko)" || echo "    [WARN] Failed to load kernel module"
else
    echo "    [WARN] Kernel module not found at $MOD_PATH"
fi"""

        verify_snippet = ""
        verify_commands = config.get('verify_commands', [])
        if verify_commands:
            verify_cmds_bash = ""
            for cmd in verify_commands:
                verify_cmds_bash += f"""
    echo "    Running: {cmd}"
    if {cmd}; then
        echo "      -> PASS"
    else
        echo "      -> FAIL (Warning only)"
    fi"""
            verify_snippet = f"""
echo "[*] Running post-install verification..."{verify_cmds_bash}
"""

        content = template.replace('{pkg_name}', pkg_name)
        content = content.replace('# __PAYLOAD_INSTALL_SNIPPET__', payload_install_snippet)
        content = content.replace('# __KERNEL_MODULE_SNIPPET__', kernel_module_snippet)
        content = content.replace('# __VERIFY_SNIPPET__', verify_snippet)

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
