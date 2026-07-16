```markdown
# ARM64 Cross-Architecture Offline Packager

A specialized deployment engine designed to bundle ARM64 (`aarch64`) compiled applications—including complex directory toolchains and Python projects—into standalone `.deb` installers.

This tool is engineered to run natively on an internet-connected AMD64 host. It safely executes cross-architecture dependency resolution and fetches ARM64 assets without modifying the host machine's native packages. The output is a self-contained artifact that installs autonomously on an air-gapped target node.

---

## System Architecture Requirements

To successfully package and deploy software, the build and deployment environments must meet the following baseline specifications:

| Environment | Architecture | Network State | Required Packages & Core Tools | 
| ----- | ----- | ----- | ----- | 
| **Build Host** | `amd64` (x86_64) | **Online** | Python 3.6+, `binutils` (provides `readelf`), `dpkg`, `apt-cache`, `apt-get`. Must be a Debian/Ubuntu OS. | 
| **Target Node** | `arm64` (aarch64) | **Air-Gapped** | `dpkg` (Standard on all Debian/Ubuntu systems). No internet access required. | 

> **OS Parity Requirement:** For maximum stability, the AMD64 Build Host should run the same major OS distribution version (e.g., Ubuntu 22.04 LTS) as the Target Node. This guarantees kernel and C-runtime (`glibc`) compatibility when targeted libraries are fetched from the upstream repositories.

---

## Theoretical Foundations

To circumvent the limitations of standard cross-compilation packaging, this platform leverages the native structural mechanics of Debian packages. 

The output `.deb` file acts as a delivery mechanism. It contains:
1. **`DEBIAN/control`**: Dynamically generated metadata enforcing the `Architecture: arm64` constraint.
2. **`data.tar` Structure**: The core executable binaries mapped to `/usr/bin/` and a nested cache of cross-downloaded `.deb` dependencies stored securely inside `/opt/airgap/<name>/deps/`.
3. **`DEBIAN/postinst` Script**: A maintainer script injected into the package. Upon installation on the target machine, this script extracts the nested dependencies and invokes `dpkg -i` to install them locally before finalizing the deployment via `ldconfig`.

---

## The 5-Stage Packaging Pipeline

The system follows a strictly linear, pipeline-based architecture:

1. **Input Ingestion (`main.py`):** An interactive CLI validates the input modality (binary path, project folder, or installed package). It performs mandatory string sanitization to strip invisible whitespace and carriage returns, preventing `dpkg-deb` from encountering malformed field errors during compilation.

2. **Static Analysis (`analyzer.py`):** Traditional dynamic analysis (`ldd`) crashes when executed against foreign architectures. Instead, the analyzer employs `readelf -d` to statically parse the ELF headers and extract `(NEEDED)` shared libraries. It filters out virtual kernel objects (e.g., `linux-vdso.so.1`) and maps the remaining logical libraries to their root Debian packages using `dpkg -S`.

3. **BFS Resolution (`resolver.py`):** The system queries `apt-cache depends <package>:arm64` to establish the dependency graph. It utilizes a Breadth-First Search (BFS) to map the entire target tree, capturing both `Depends` and `PreDepends`. It actively filters out optional bloat (`--recommends`, `--suggests`), meta-packages, and core system essentials (e.g., `base-files`) while tracking visited nodes to prevent circular loops.

4. **Cross-Acquisition (`downloader.py`):** The module forces multi-architecture downloads by appending the `:arm64` suffix to `apt-get download` requests. This forces the repository mirrors to deliver `aarch64` compiled binaries into a local staging cache without installing them on the AMD64 host.

5. **Assembly (`builder.py`):** Structures the cache into a Debian root filesystem layout, dynamically generates the metadata, injects the executable installer scripts (`chmod 0o755`), and compiles the final `.deb` artifact using `dpkg-deb --build`.

---

## Execution Guide (Required Linux Commands)

### Phase 1: Building the Package (On AMD64 Host)

Launch the centralized interactive orchestrator from the root directory. The system will handle path expansion (e.g., `~/`) automatically.

```bash
# 1. Navigate to the packager workspace
cd ~/python-arm64-packager

# 2. Launch the interactive orchestration wizard
python3 main.py

```

**Wizard Prompts:**

* **Target Architecture:** Select `[2]` for `arm64`.
* **Input Pathway:** Select `[1]` for Binary/Directory or `[2]` for Project Source.
* **Target Path:** Provide the absolute or relative path (e.g., `~/PF_RING/userland/examples`).
* **Metadata Initialization:** Input the required package name, version, and a brief description.

### Phase 2: Deploying the Package (On ARM64 Target)

Transfer the generated `.deb` file (via USB or secure physical media) to the isolated target machine.

```bash
# 1. Standard offline installation via the Debian Package Manager
sudo dpkg -i pfring-suite_1.0.0_arm64.deb

```

**Troubleshooting & File Conflicts:**
If you are upgrading an existing package and `dpkg` halts with a *"trying to overwrite /usr/bin/..."* or *"Broken pipe"* error due to ownership collisions with legacy installations, force the transition safely using:

```bash
sudo dpkg -i --force-overwrite pfring-suite_1.0.0_arm64.deb

```

*(Optional)* **Post-Install Verification for Network Tools:**
For tools requiring network socket binding, identify the active network interface and execute the payload:

```bash
ip a
sudo pfcount -i eth0

```

---

## Validation Scenarios (Test Cases)

### Test Case A: Multi-Binary Directory Extraction (PF_RING Framework)

* **Context:** PF_RING is a high-speed network packet capture framework that bypasses standard kernel stacks. Its utilities require complex low-level C libraries (e.g., `libnuma` for memory architecture and `libnl` for Netlink sockets) that are rarely present on minimal air-gapped target installations.
* **Objective:** Verify the tool can scan an entire framework directory, extract multiple executables, and map complex low-level dependencies natively.
* **Execution:** Pointed the wizard (Option `[1] Binary/Directory`) to `~/PF_RING/userland/examples`.
* **System Response:**
* Recursively scanned the directory, successfully bypassing `Makefile`, `.c`, and `.h` source files.
* Identified 16 distinct ELF binaries (including `pfcount`, `pfsend`, `pfbridge`).
* `readelf` statically identified critical kernel/memory libraries (`libc.so.6`, `libnl-3.so.200`, `libnuma.so.1`).
* Mapped these files to standard Debian packages (`libc6`, `libnl-3-20`, `libnuma1`) and resolved their sub-dependencies.
* *Note:* The system logged a controlled failure for host cross-compilers (`libc6-arm64-cross`), correctly ignoring it as native ARM64 targets do not require cross-compilation suites to execute.


* **Result:** Output a unified `pfring-suite_1.0.0_arm64.deb`. Upon execution of `dpkg -i` on the target node, the `postinst` script executed `ldconfig` to register the bundled dependencies, allowing `pfcount` to execute instantly and bind to `eth0`.

### Test Case B: Offline Python Project Bundling

* **Objective:** Verify the tool can package Python source code and successfully cross-fetch ARM64 wheel dependencies while running on an AMD64 host.
* **Execution:** Pointed the wizard (Option `[2] Project Source`) to a Python workspace containing a valid `requirements.txt` manifest.
* **System Response:**
* Detected the Python execution flow based on user selection.
* Executed `pip download --only-binary=:all: --platform manylinux2014_aarch64` to pull architecture-specific `.whl` files into a local staging `vendor/` directory, bypassing host installation.
* Dynamically configured the `postinst` installer script for a Python-specific payload deployment.


* **Result:** Output a `.deb` package. When deployed on the offline target node, the embedded `postinst` script successfully executed `pip3 install --no-index --find-links=vendor/`, ensuring the Python application was operational without attempting to reach the public PyPI indexing servers.

---

## Known Limitations and Future Scope

While highly robust for standard deployments, system administrators should be aware of the following architectural constraints:

1. **Pre-Compilation Requirement:** This tool packages software; it does not compile it. ARM64 `C/C++` binaries must be natively cross-compiled for `aarch64` prior to passing them to this packager. Analyzing raw AMD64 binaries will result in target execution failures.
2. **Glibc Version Pinning:** Because the tool fetches packages from the build host's configured mirrors, severe version mismatches (especially with core runtime libraries like `libc6`/`glibc`) between the host and target can cause execution faults on the deployed machine. Strict OS version parity is recommended.
3. **System Service Daemons:** If packaged binaries require dedicated `systemd` services to launch automatically on boot, those `.service` files currently must be added manually to the staging directories prior to the final assembly phase.
4. **Cross-Compiler Artifact Logging:** During analysis, the system may log warnings regarding host cross-compiler packages (e.g., `libc6-arm64-cross`) failing to download via `apt-get`. This is expected behavior and will not impact final target deployment.
5. **Distribution Lock:** Currently, the resolution engine is rigidly coupled to Debian/Ubuntu package managers (`dpkg` and `apt-cache`). Expanding this framework to support `rpm` (RedHat/CentOS) or `pacman` (Arch) would require further abstraction of the underlying system calls.

```

```