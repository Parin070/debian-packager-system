#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import subprocess

from analyzer import Analyzer
from downloader import Downloader
from builder import Builder

def get_package_binary(package_name):
    """Locates standard system executable path bound to an installed package."""
    try:
        result = subprocess.run(['dpkg', '-L', package_name], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        print(f"[ERROR] Package '{package_name}' is not present on this host.")
        sys.exit(1)
    bin_dirs = ['/usr/bin/', '/usr/sbin/', '/usr/local/bin/', '/bin/', '/sbin/']
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if any(line.startswith(d) for d in bin_dirs) and os.path.isfile(line) and os.access(line, os.X_OK):
            return line
    print(f"[ERROR] No executable binary matched for package '{package_name}'.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Unified Python & Binary ARM64 Air-Gapped Packager")
    
    # Create mutually exclusive group for handling the three different inputs
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--path", help="Path to your raw Python project directory.")
    input_group.add_argument("--binary", help="Path to a dynamically linked system ELF binary executable.")
    input_group.add_argument("--package", help="Name of an already-installed Debian package to bundle.")
    
    parser.add_argument("--name", help="Custom name identifier for your output package.")
    parser.add_argument("--version", default="1.0.0", help="Version identifier (Default: 1.0.0)")
    parser.add_argument("--description", default="Packaged ARM64 isolated app bundle", help="Description details")
    
    args = parser.parse_args()
    
    print("==========================================================")
    print("      INITIALIZING UNIFIED ARM64 AIR-GAP CONVERSION       ")
    print("==========================================================")
    
    analyzer = Analyzer()
    downloader = Downloader()
    builder = Builder()
    
    binary_path = None
    project_path = None
    pkg_name = args.name
    
    # --- FLOW A: Python source handling ---
    if args.path:
        project_path = os.path.abspath(args.path)
        if not analyzer.analyze_source(project_path):
            sys.exit(1)
        if not pkg_name:
            pkg_name = os.path.basename(project_path)
            
        temp_vendor_cache = f"./tmp_vendor_cache_{pkg_name}"
        if not downloader.download_arm64_wheels(project_path, temp_vendor_cache):
            shutil.rmtree(temp_vendor_cache, ignore_errors=True)
            sys.exit(1)
            
        output_deb = f"{pkg_name}_{args.version}_arm64.deb"
        success = builder.build_package(
            pkg_name=pkg_name, version=args.version, description=args.description,
            output_path=output_deb, project_path=project_path, vendor_dir=temp_vendor_cache
        )
        shutil.rmtree(temp_vendor_cache, ignore_errors=True)

    # --- FLOW B & C: System Binary / Debian Package handling ---
    else:
        if args.binary:
            binary_path = os.path.abspath(args.binary)
        elif args.package:
            print(f"[*] Resolving system binary path bound to package: {args.package}")
            binary_path = get_package_binary(args.package)
            
        if not os.path.isfile(binary_path):
            print(f"[-] Error: Binary target path not found: {binary_path}")
            sys.exit(1)
            
        if not pkg_name:
            pkg_name = os.path.basename(binary_path)
            
        # Analyze the binary libraries and download equivalent system .deb files for ARM64
        discovered_packages = analyzer.analyze_binary_deps(binary_path)
        if args.package:
            discovered_packages.add(args.package)
            
        temp_vendor_cache = f"./tmp_vendor_cache_{pkg_name}"
        downloader.download_arm64_debs(discovered_packages, temp_vendor_cache)
        
        output_deb = f"{pkg_name}_{args.version}_arm64.deb"
        success = builder.build_package(
            pkg_name=pkg_name, version=args.version, description=args.description,
            output_path=output_deb, binary_path=binary_path, vendor_dir=temp_vendor_cache
        )
        shutil.rmtree(temp_vendor_cache, ignore_errors=True)
        
    if success:
        print(f"\n[SUCCESS] Custom packaging complete. Final file: {output_deb}")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()