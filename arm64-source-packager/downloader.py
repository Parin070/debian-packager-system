#!/usr/bin/env python3
import os
import subprocess
import sys

class Downloader:
    def download_arm64_wheels(self, project_path, target_vendor_dir):
        """Forces pip to download arm64-specific wheel binaries if requirements.txt exists."""
        req_file = os.path.join(project_path, "requirements.txt")
        
        if not os.path.exists(req_file):
            print("[INFO] Skipping wheel download phase (no external dependencies listed).")
            return True
            
        os.makedirs(target_vendor_dir, exist_ok=True)
        print(f"[*] Querying PyPI for explicit ARM64 wheels into: {target_vendor_dir}")
        
        cmd = [
            sys.executable, "-m", "pip", "download",
            "--only-binary=:all:",
            "--platform", "manylinux2014_aarch64",
            "--implementation", "cp",
            "-r", req_file,
            "-d", target_vendor_dir
        ]
        try:
            subprocess.run(cmd, check=True)
            print("[+] Successfully gathered matching ARM64 dependencies.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[-] Error during pip cross-architecture download: {e}")
            return False

    def download_arm64_debs(self, package_set, target_vendor_dir):
        """Uses apt-get download to gather arm64 .deb packages on an amd64 host."""
        os.makedirs(target_vendor_dir, exist_ok=True)
        print(f"[*] Downloading {len(package_set)} system packages (:arm64) into staging vendor layout...")
        
        success_count = 0
        for pkg in sorted(package_set):
            # Explicitly force arm64 cross-architecture package targets
            arm64_pkg_name = f"{pkg}:arm64"
            print(f"    -> Downloading: {arm64_pkg_name} ", end='', flush=True)
            try:
                # Run apt-get download in the designated target directory
                subprocess.run(['apt-get', 'download', arm64_pkg_name], 
                               capture_output=True, text=True, check=True, cwd=target_vendor_dir)
                print("✓")
                success_count += 1
            except subprocess.CalledProcessError:
                print("✗ (Failed to download via apt)")
                
        return success_count > 0