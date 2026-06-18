#!/usr/bin/env python3
import os
import subprocess
import sys

class Downloader:
    def download_arm64_wheels(self, project_path, target_vendor_dir):
        """Forces pip to download arm64-specific wheel binaries."""
        req_file = os.path.join(project_path, "requirements.txt")
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
