#!/usr/bin/env python3
import os
import shutil
import subprocess

# Define the templates directory path locally within this module
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

class Builder:
    def build_package(self, pkg_name, version, description, output_path, project_path=None, binary_path=None, vendor_dir=None):
        """Assembles either a Python source layout or an ELF binary payload structure into a .deb."""
        build_root = f"./tmp_build_{pkg_name}"
        
        # 1. Clean existing temporary workspaces completely
        if os.path.exists(build_root):
            shutil.rmtree(build_root)
            
        os.makedirs(build_root, exist_ok=True)
        
        # 2. Stage target project payload application files first
        if project_path:
            share_dir = os.path.join(build_root, "usr", "share", pkg_name)
            os.makedirs(share_dir, exist_ok=True)
            shutil.copytree(project_path, share_dir, dirs_exist_ok=True)
            if vendor_dir and os.path.exists(vendor_dir):
                shutil.copytree(vendor_dir, os.path.join(share_dir, "vendor"), dirs_exist_ok=True)

        # 3. Stage system binary payloads if selected
        elif binary_path:
            opt_deps = os.path.join(build_root, "opt", "airgap", pkg_name, "deps")
            opt_payload = os.path.join(build_root, "opt", "airgap", pkg_name, "payload")
            os.makedirs(opt_deps, exist_ok=True)
            os.makedirs(opt_payload, exist_ok=True)
            
            shutil.copy2(binary_path, os.path.join(opt_payload, os.path.basename(binary_path)))
            os.chmod(os.path.join(opt_payload, os.path.basename(binary_path)), 0o755)
            
            if vendor_dir and os.path.exists(vendor_dir):
                for f in os.listdir(vendor_dir):
                    if f.endswith('.deb'):
                        shutil.copy2(os.path.join(vendor_dir, f), os.path.join(opt_deps, f))

        # 4. NOW create the DEBIAN metadata control folder (Safe from payload copies)
        debian_dir = os.path.join(build_root, "DEBIAN")
        os.makedirs(debian_dir, exist_ok=True)

        # 5. Compile DEBIAN/control metadata template configuration
        with open(os.path.join(TEMPLATES_DIR, "control"), "r") as f:
            control_content = f.read()
        control_content = control_content.replace("#PKG_NAME#", pkg_name).replace("#VERSION#", version).replace("#DESCRIPTION#", description)
        with open(os.path.join(debian_dir, "control"), "w") as f:
            f.write(control_content)
            
        # 6. Compile DEBIAN/postinst script template configuration
        with open(os.path.join(TEMPLATES_DIR, "postinst"), "r") as f:
            postinst_content = f.read()
        postinst_content = postinst_content.replace("#PKG_NAME#", pkg_name)
        if binary_path:
            postinst_content = postinst_content.replace("{binary_name}", os.path.basename(binary_path))
            
        postinst_path = os.path.join(debian_dir, "postinst")
        with open(postinst_path, "w") as f:
            f.write(postinst_content)
        os.chmod(postinst_path, 0o755)
        
        # 7. Trigger dpkg compilation
        print(f"[*] Invoking dpkg-deb to compile package: {output_path}")
        try:
            subprocess.run(["dpkg-deb", "--build", build_root, output_path], check=True)
            print(f"[+] Package assembly complete: {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[-] dpkg compilation failed: {e}")
            return False
        finally:
            if os.path.exists(build_root):
                shutil.rmtree(build_root)