#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import subprocess
import re

from analyzer import Analyzer
from resolver import Resolver
from downloader import Downloader
from builder import Builder

def is_elf_binary(path):
    """Check if a file is an ELF binary by reading its magic bytes."""
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
        return magic == b'\x7fELF'
    except (IOError, PermissionError):
        return False

def find_binaries_in_dir(dir_path):
    """Recursively search for and return all executable ELF binaries in a directory."""
    candidates = []
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            fpath = os.path.join(root, f)
            # Exclude source, headers, and intermediate build objects
            if os.access(fpath, os.X_OK) and not f.endswith(('.py', '.sh', '.md', '.txt', '.cfg', '.ini', '.h', '.c', '.cpp', '.o', '.a', '.la', '.lo')):
                if is_elf_binary(fpath):
                    candidates.append(fpath)
    return candidates

def get_package_binary(package_name):
    try:
        result = subprocess.run(['dpkg', '-L', package_name], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        print(f"[ERROR] Package '{package_name}' is not found on this build host.")
        sys.exit(1)
    bin_dirs = ['/usr/bin/', '/usr/sbin/', '/usr/local/bin/', '/bin/', '/sbin/']
    binaries = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if any(line.startswith(d) for d in bin_dirs) and os.path.isfile(line) and os.access(line, os.X_OK):
            binaries.append(line)
    if not binaries:
        print(f"[ERROR] No matching global executable found for package '{package_name}'.")
        sys.exit(1)
    return binaries

def main():
    parser = argparse.ArgumentParser(description="Universal ARM64 Air-Gapped Package System")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--path", help="Path to Python source directory layout.")
    input_group.add_argument("--binary", nargs='+', help="Path(s) to ELF binaries or directory containing binaries.")
    input_group.add_argument("--package", help="Name of a Debian package to mirror recursively.")
    
    parser.add_argument("--name", help="Custom name assignment identifier for your output package.")
    parser.add_argument("--version", default="1.0.0", help="Version identifier string (Default: 1.0.0)")
    parser.add_argument("--description", default="Universal ARM64 offline application bundle", help="Description parameters")
    
    args = parser.parse_args()
    
    analyzer = Analyzer()
    resolver = Resolver()
    downloader = Downloader()
    builder = Builder()
    
    binary_paths = []
    project_path = None
    
    pkg_name = args.name.strip().replace('\n', '').replace('\r', '') if args.name else None
    pkg_version = args.version.strip().replace('\n', '').replace('\r', '')
    pkg_description = args.description.strip().replace('\n', ' ').replace('\r', ' ')

    if args.path:
        project_path = os.path.abspath(args.path)
        if not analyzer.analyze_source(project_path):
            sys.exit(1)
        if not pkg_name:
            pkg_name = os.path.basename(project_path).strip().replace('\n', '').replace('\r', '')
            
        pkg_name = re.sub(r'[^a-z0-9\-\+\.]', '-', pkg_name.lower()).strip('-')
        temp_cache = f"./tmp_vendor_cache_{pkg_name}"
        if not downloader.download_arm64_wheels(project_path, temp_cache):
            shutil.rmtree(temp_cache, ignore_errors=True)
            sys.exit(1)
            
        output_deb = f"{pkg_name}_{pkg_version}_arm64.deb"
        success = builder.build_package(
            pkg_name=pkg_name, version=pkg_version, description=pkg_description,
            output_path=output_deb, project_path=project_path, vendor_dir=temp_cache
        )
        shutil.rmtree(temp_cache, ignore_errors=True)

    else:
        if args.binary:
            resolved_paths = []
            for item in args.binary:
                abs_item = os.path.abspath(item)
                if os.path.isdir(abs_item):
                    print(f"[*] Input target is a directory. Scanning for ELF binaries inside: {abs_item}")
                    found = find_binaries_in_dir(abs_item)
                    print(f"    -> Successfully discovered {len(found)} compiled binary executable(s).")
                    resolved_paths.extend(found)
                elif os.path.isfile(abs_item):
                    if is_elf_binary(abs_item):
                        resolved_paths.append(abs_item)
                    else:
                        print(f"[WARN] Skipping non-ELF file: {abs_item}")
            binary_paths = resolved_paths

            if not binary_paths:
                print("[ERROR] Failed to discover any valid compiled ELF binaries in the specified targets.")
                sys.exit(1)
                
        elif args.package:
            print(f"[*] Resolving system binaries tracked inside package: {args.package}")
            binary_paths = get_package_binary(args.package)
            
        if not pkg_name:
            pkg_name = os.path.basename(binary_paths[0]).strip().replace('\n', '').replace('\r', '')
            
        pkg_name = re.sub(r'[^a-z0-9\-\+\.]', '-', pkg_name.lower()).strip('-')
        
        # Pass the newly discovered array of files directly to the analyzer
        seed_packages = analyzer.analyze_binary_deps(binary_paths)
        if args.package:
            seed_packages.add(args.package.strip().replace('\n', '').replace('\r', ''))
            
        all_deps = resolver.resolve(seed_packages)
        
        temp_cache = f"./tmp_vendor_cache_{pkg_name}"
        downloader.download_arm64_debs(all_deps, temp_cache)
        
        output_deb = f"{pkg_name}_{pkg_version}_arm64.deb"
        success = builder.build_package(
            pkg_name=pkg_name, version=pkg_version, description=pkg_description,
            output_path=output_deb, binary_paths=binary_paths, vendor_dir=temp_cache
        )
        shutil.rmtree(temp_cache, ignore_errors=True)

    if success:
        print(f"\n[SUCCESS] Universal ARM64 bundle complete. Target file: {output_deb}")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()