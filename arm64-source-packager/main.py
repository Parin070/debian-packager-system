#!/usr/bin/env python3
import argparse
import os
import shutil
import sys

from analyzer import Analyzer
from downloader import Downloader
from builder import Builder

def main():
    parser = argparse.ArgumentParser(description="Python Source Code to ARM64 Air-Gapped Packager")
    parser.add_argument("--path", required=True, help="Path to your raw Python project directory.")
    parser.add_argument("--name", required=True, help="The deployment name for your application package.")
    parser.add_argument("--version", default="1.0.0", help="Version identifier (Default: 1.0.0)")
    parser.add_argument("--description", default="Packaged Python app bundle", help="Description field text")
    
    args = parser.parse_args()
    
    print("==========================================================")
    print("      INITIALIZING PYTHON ARM64 AIR-GAP CONVERSION        ")
    print("==========================================================")
    
    # Pipeline Step 1: Analyze Input Assets
    analyzer = Analyzer()
    if not analyzer.analyze_source(args.path):
        sys.exit(1)
        
    # Set up temporary vendor cache path
    temp_vendor_cache = f"./tmp_vendor_cache_{args.name}"
    
    # Pipeline Step 2: Extract Remote ARM64 Wheels
    downloader = Downloader()
    if not downloader.download_arm64_wheels(args.path, temp_vendor_cache):
        if os.path.exists(temp_vendor_cache):
            shutil.rmtree(temp_vendor_cache)
        sys.exit(1)
        
    # Pipeline Step 3: Bundle and Compile Debian Staging Packages
    output_deb = f"{args.name}_{args.version}_arm64.deb"
    builder = Builder()
    success = builder.build_package(
        project_path=args.path,
        pkg_name=args.name,
        version=args.version,
        description=args.description,
        vendor_dir=temp_vendor_cache,
        output_path=output_deb
    )
    
    # Clean up local wheel download cache
    if os.path.exists(temp_vendor_cache):
        shutil.rmtree(temp_vendor_cache)
        
    if success:
        print(f"\n[SUCCESS] Custom packaging complete. Final file: {output_deb}")
    else:
        print("\n[-] Packaging engine encountered build errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
