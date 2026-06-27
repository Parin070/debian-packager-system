#!/usr/bin/env python3
import os
import shutil
import subprocess

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

class Builder:
    def build_package(self, pkg_name, version, description, output_path, project_path=None, binary_paths=None, vendor_dir=None):
        build_root = f"./tmp_build_{pkg_name}"
        if os.path.exists(build_root):
            shutil.rmtree(build_root)
        os.makedirs(build_root, exist_ok=True)

        payload_type = "Binary"

        # FLOW A: Python Project Staging
        if project_path:
            payload_type = "Python"
            share_dir = os.path.join(build_root, "usr", "share", pkg_name)
            os.makedirs(share_dir, exist_ok=True)
            shutil.copytree(project_path, share_dir, dirs_exist_ok=True)
            if vendor_dir and os.path.exists(vendor_dir):
                shutil.copytree(vendor_dir, os.path.join(share_dir, "vendor"), dirs_exist_ok=True)

        # FLOW B & C: Universal Compiled Binaries, Libraries, and Packages
        elif binary_paths:
            bin_dir = os.path.join(build_root, "usr", "bin")
            os.makedirs(bin_dir, exist_ok=True)
            
            for b_path in binary_paths:
                target_name = os.path.basename(b_path)
                shutil.copy2(b_path, os.path.join(bin_dir, target_name))
                os.chmod(os.path.join(bin_dir, target_name), 0o755)

            opt_deps = os.path.join(build_root, "opt", "airgap", pkg_name, "deps")
            os.makedirs(opt_deps, exist_ok=True)
            if vendor_dir and os.path.exists(vendor_dir):
                for f in os.listdir(vendor_dir):
                    if f.endswith('.deb'):
                        shutil.copy2(os.path.join(vendor_dir, f), os.path.join(opt_deps, f))

        # Metadata Assembly
        debian_dir = os.path.join(build_root, "DEBIAN")
        os.makedirs(debian_dir, exist_ok=True)

        # FIX: Directly writing the control file with the mandatory Maintainer field
        control_content = (
            f"Package: {pkg_name}\n"
            f"Version: {version}\n"
            f"Architecture: arm64\n"
            f"Maintainer: Airgap Admin <admin@localhost>\n"
            f"Description: {description}\n"
        )
        with open(os.path.join(debian_dir, "control"), "w", newline='\n') as f:
            f.write(control_content)

        # Render DEBIAN/postinst
        with open(os.path.join(TEMPLATES_DIR, "postinst"), "r") as f:
            postinst_template = f.read()
        
        postinst_runtime = postinst_template.replace("#PKG_NAME#", pkg_name).replace("#PAYLOAD_TYPE#", payload_type)
        postinst_path = os.path.join(debian_dir, "postinst")
        with open(postinst_path, "w", newline='\n') as f:
            f.write(postinst_runtime)
        os.chmod(postinst_path, 0o755)

        print(f"[*] Assembling package via dpkg-deb for arm64 target architecture...")
        try:
            subprocess.run(["dpkg-deb", "--build", build_root, output_path], check=True)
            print(f"[SUCCESS] Package built successfully: {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[-] Package assembly failed: {e}")
            return False
        finally:
            if os.path.exists(build_root):
                shutil.rmtree(build_root)