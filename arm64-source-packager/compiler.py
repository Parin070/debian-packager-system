import subprocess
import os
import sys

class Compiler:
    def __init__(self):
        # Define the cross-compiler toolchain
        self.cc = "aarch64-linux-gnu-gcc"
        self.cxx = "aarch64-linux-gnu-g++"

    def cross_compile_make(self, source_dir):
        """Runs make with the ARM64 cross-compiler in the target directory."""
        print(f"[*] Initiating ARM64 cross-compilation in: {source_dir}")
        
        # Verify the toolchain is installed
        if not shutil.which(self.cc):
            print(f"[ERROR] Cross-compiler '{self.cc}' not found. Run: sudo apt install gcc-aarch64-linux-gnu")
            sys.exit(1)

        try:
            # First, clean any old AMD64 binaries
            subprocess.run(['make', 'clean'], cwd=source_dir, check=False, capture_output=True)
            
            # Run make with the CC override
            print(f"[*] Running: make CC={self.cc}")
            subprocess.run(['make', f'CC={self.cc}'], cwd=source_dir, check=True)
            print("[SUCCESS] Cross-compilation completed.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Cross-compilation failed: {e}")
            sys.exit(1)