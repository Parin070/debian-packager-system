#!/usr/bin/env python3
import os
import shutil
import subprocess

class Builder:
    def build_package(self, project_path, pkg_name, version, description, vendor_dir, output_path):
        """Assembles the package framework, updates template values, and builds the .deb."""
        build_root = f"./tmp_build_{pkg_name}"
        share_dir = os.path.join(build_root, "usr", "share", pkg_name)
        debian_dir = os.path.join(build_root, "DEBIAN")
        
        # Clean existing temporary workspaces
        if os.path.exists(build_root):
            shutil.rmtree(build_root)
            
        os.makedirs(share_dir, exist_ok=True)
        os.makedirs(debian_dir, exist_ok=True)
        
        # 1. Stage project application files and pre-fetched wheels
        shutil.copytree(project_path, share_dir, dirs_exist_ok=True)
        shutil.copytree(vendor_dir, os.path.join(share_dir, "vendor"), dirs_exist_ok=True)
        
        # 2. Compile control metadata from template
        with open("templates/control", "r") as f:
            control_content = f.read()
        control_content = control_content.replace("#PKG_NAME#", pkg_name)
        control_content = control_content.replace("#VERSION#", version)
        control_content = control_content.replace("#DESCRIPTION#", description)
        
        with open(os.path.join(debian_dir, "control"), "w") as f:
            f.write(control_content)
            
        # 3. Compile postinst script from template
        with open("templates/postinst", "r") as f:
            postinst_content = f.read()
        postinst_content = postinst_content.replace("#PKG_NAME#", pkg_name)
        
        postinst_path = os.path.join(debian_dir, "postinst")
        with open(postinst_path, "w") as f:
            f.write(postinst_content)
            
        os.chmod(postinst_path, 0o755) # Force required execution flags
        
        # 4. Trigger dpkg compilation
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
