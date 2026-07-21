# ARM64 Cross-Architecture Offline Packager

A specialized deployment engine designed to bundle ARM64 (aarch64) compiled applications—including complex directory toolchains and Python projects—into standalone `.deb` installers.

This tool is engineered to run natively on an internet-connected AMD64 host. It safely executes cross-architecture dependency resolution and fetches ARM64 assets without modifying the host machine's native packages. The output is a self-contained artifact that installs autonomously on an air-gapped target node.

---

## System Architecture Requirements

To successfully package and deploy software, the build and deployment environments must meet the following baseline specifications:

| Environment | Architecture | Network State | Required Packages & Core Tools |
| :--- | :--- | :--- | :--- |
| **Build Host** | `amd64` (x86_64) | Online | Python 3.6+, `binutils` (provides `readelf`), `dpkg`, `apt-cache`, `apt-get`, cross-compiler (`aarch64-linux-gnu-gcc`). Must be a Debian/Ubuntu OS. |
| **Target Node** | `arm64` (aarch64) | Air-Gapped | `dpkg` (Standard on all Debian/Ubuntu systems). No internet access required. |

> **OS Parity Requirement:** For maximum stability, the AMD64 Build Host should run the same major OS distribution version (e.g., Ubuntu 22.04 LTS) as the Target Node. This guarantees kernel and C-runtime (`glibc`) compatibility when targeted libraries are fetched from the upstream repositories.

---

## Theoretical Foundations

To circumvent the limitations of standard cross-compilation packaging, this platform leverages the native structural mechanics of Debian packages. 

The output `.deb` file acts as a delivery mechanism. It contains:

*   **`DEBIAN/control`:** Dynamically generated metadata enforcing the `Architecture: arm64` constraint.
*   **`data.tar` Structure:** The core executable binaries mapped safely to `/usr/local/bin/` (preventing core OS command collisions) and a nested cache of cross-downloaded `.deb` and `.whl` dependencies stored securely inside `/opt/airgap/<name>/deps/`.
*   **`DEBIAN/postinst` Script:** A maintainer script injected into the package. To bypass `dpkg` frontend locks safely, this script spawns a detached background daemon upon installation on the target machine. This daemon extracts the nested dependencies, invokes `dpkg -i` to install system libraries, runs `pip3 install --no-index` for offline Python wheels, and finalizes the deployment via `ldconfig`.

---

## The 6-Stage Packaging Pipeline

The system follows a strictly linear, pipeline-based architecture:

1.  **Input Ingestion (`main.py`):** An interactive CLI validates the input modality (binary path, project folder, or installed package). It takes the target system architecture (`arm64`), the type of input, and the package metadata. It performs mandatory string sanitization to strip invisible whitespace and carriage returns, preventing `dpkg-deb` from encountering malformed field errors during compilation.
2.  **Cross-Compilation (`compiler.py`):** Based on the input type detected in the previous step, if the user provides raw source code (such as C or C++) rather than a pre-compiled executable, this stage invokes the cross-compiler (e.g., `aarch64-linux-gnu-gcc`). Its exact role is to translate the high-level, human-readable source code into low-level ARM64 machine code. Because the host system runs on AMD64, the cross-compiler explicitly targets the ARM architecture to ensure the resulting 1s and 0s are physically readable by the isolated VM.
3.  **Static Analysis (`analyzer.py`):** Traditional dynamic analysis (`ldd`) crashes when executed against foreign architectures. Instead, the analyzer employs `readelf -d` to statically parse the ELF headers of the binary and extract `(NEEDED)` shared libraries (`.so`). It filters out virtual kernel objects (e.g., `linux-vdso.so.1`) and maps the remaining logical libraries to their root Debian packages using `dpkg -S`.
4.  **BFS Resolution (`resolver.py`):** The system queries `apt-cache depends <package>:arm64` to establish the dependency graph. It utilizes a Breadth-First Search (BFS) to map out every single sub-dependency required by the code. **Crucially, it references a strict `SYSTEM_BLACKLIST` to actively filter out core OS essentials (e.g., `libc6`, `systemd`, `libpam0g`)**, preventing the packager from overwriting foundational target machine drivers and corrupting the VM.
5.  **Cross-Acquisition (`downloader.py`):** This module forces multi-architecture downloads by appending the `:arm64` suffix to `apt-get download <package>:arm64` requests. For Python projects, it runs `pip download --platform aarch64`. This forces the Ubuntu servers to deliver `aarch64` compiled binaries into a local temporary staging folder, avoiding installation on the AMD64 host and protecting the host machine from cross-architecture corruption.
6.  **Assembly (`builder.py`):** Structures the cache into a simulated Linux root filesystem layout, placing binaries in the collision-safe `/usr/local/bin/` and bundling downloaded `.deb`, `.whl`, and `.tar.gz` dependencies inside `/opt/airgap/`. It dynamically generates metadata, injects executable installer scripts (`chmod 0o755`), and compiles the final wrapper using `dpkg-deb --build`.

---

## Execution Guide

### Phase 1: Building the Package (On AMD64 Host)
Launch the centralized interactive orchestrator from the root directory. The system will handle path expansion (e.g., `~/`) automatically.

```bash
# 1. Navigate to the packager workspace
cd ~/python-arm64-packager

# 2. Launch the interactive orchestration wizard
python3 main.py

```

**Wizard Prompts:**

* **Target Architecture:** Select `[2]` for arm64.
* **Input Pathway:** Select `[1]` for Binary/Directory or `[2]` for Project Source.
* **Target Path:** Provide the absolute or relative path (e.g., `~/PF_RING/userland/examples`).
* **Metadata Initialization:** Input the required package name, version, and a brief description.

### Phase 2: Deploying the Package (On ARM64 Target)

Transfer the generated `.deb` file (via USB, secure physical media, or SCP) to the isolated target machine.

```bash
# Standard offline installation via the Debian Package Manager
sudo dpkg -i pfring-suite_1.0.0_arm64.deb

```

> **[!] CRITICAL EXECUTION WARNING:**
> Because the package utilizes a detached background daemon to bypass `dpkg` locks, the terminal prompt will return immediately. **Do not execute your software right away.** Wait 10-15 seconds for the daemon to silently finish unpacking core dependencies and refreshing the `ldconfig` cache in the background.

**Troubleshooting & File Conflicts:**
If you are upgrading an existing package and `dpkg` halts with a "trying to overwrite..." or "Broken pipe" error due to ownership collisions with legacy installations, force the transition safely using:

```bash
sudo dpkg -i --force-overwrite pfring-suite_1.0.0_arm64.deb

```

**(Optional) Post-Install Verification for Network Tools:**
For tools requiring network socket binding, identify the active network interface and execute the payload:

```bash
ip a
sudo pfcount -i eth0

```

---

## Validation Scenarios (Test Cases)

### Test Case A: Multi-Binary Directory Extraction (PF_RING Framework)

* **Context:** PF_RING is a high-speed network packet capture framework that bypasses standard kernel stacks. Its utilities require complex low-level C libraries (e.g., `libnuma` for memory architecture and `libnl` for Netlink sockets) that are rarely present on minimal air-gapped target installations.
* **Objective:** Verify the tool can scan an entire framework directory, invoke cross-compilation (if needed), extract multiple executables, and map complex low-level dependencies natively without overwriting the core C-runtime.
* **Execution:** Pointed the wizard (Option `[1]` Binary/Directory) to `~/PF_RING/userland/examples`.
* **System Response:**
* Recursively scanned the directory and compiled `.c` source files into ARM64 executables.
* Identified 16 distinct ELF binaries (including `pfcount`, `pfsend`, `pfbridge`).
* `readelf` statically identified critical kernel/memory libraries (`libc.so.6`, `libnl-3.so.200`, `libnuma.so.1`).
* The `SYSTEM_BLACKLIST` correctly blocked `libc6` from the queue to protect the target VM from system corruption. Mapped the remaining files to standard Debian packages (`libnl-3-20`, `libnuma1`) and resolved their sub-dependencies.


* **Result:** Output a unified `pfring-suite_1.0.0_arm64.deb`. Upon execution of `dpkg -i` on the target node, the payloads were deployed safely to `/usr/local/bin/`, and the background daemon executed `ldconfig` to register the bundled dependencies, allowing `pfcount` to execute instantly and bind to `eth0`.

### Test Case B: Offline Python Project Bundling

* **Objective:** Verify the tool can package Python source code and successfully cross-fetch ARM64 wheel dependencies while running on an AMD64 host.
* **Execution:** Pointed the wizard (Option `[2]` Project Source) to a Python workspace containing a valid `requirements.txt` manifest.
* **System Response:**
* Detected the Python execution flow based on user selection.
* Executed `pip download --only-binary=:all: --platform manylinux2014_aarch64` to pull architecture-specific `.whl` files into a local staging `vendor/` directory, bypassing host installation.
* Dynamically configured the `postinst` installer script to deploy a background Python-specific installer daemon.


* **Result:** Output a `.deb` package. When deployed on the offline target node, the embedded `postinst` daemon successfully executed `pip3 install --no-index --find-links=vendor/ vendor/*.whl`, ensuring the Python application was entirely operational without attempting to reach the public PyPI indexing servers.

---

## Known Limitations and Future Scope

While highly robust for standard deployments, system administrators should be aware of the following architectural constraints:

* **Cross-Compilation Toolchains:** While the pipeline now handles source-to-binary cross-compilation during Stage 2, it assumes the AMD64 host has the required ARM toolchains (e.g., `aarch64-linux-gnu-gcc`) installed. If these are missing, compilation of raw C/C++ files will fail.
* **Glibc Version Pinning:** Because the tool fetches packages from the build host's configured mirrors, severe version mismatches between the host and target can cause execution faults on the deployed machine. Strict OS version parity is highly recommended.
* **System Service Daemons:** If packaged binaries require dedicated `systemd` services to launch automatically on boot, those `.service` files currently must be added manually to the staging directories prior to the final assembly phase.
* **Distribution Lock:** Currently, the resolution engine is rigidly coupled to Debian/Ubuntu package managers (`dpkg` and `apt-cache`). Expanding this framework to support `rpm` (RedHat/CentOS) or `pacman` (Arch) would require further abstraction of the underlying system calls.

```

```