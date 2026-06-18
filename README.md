# debian-packager-system

> Package any binary or Debian package — with all its dependencies — into a single self-contained `.deb` installable on air-gapped Ubuntu systems with zero internet access.

---

## What Is This

Air-gapped Ubuntu systems have no access to `apt` repositories or the internet. Installing software on them requires every dependency to be physically present on the machine.

`airgap-packager` solves this by:

1. Accepting a binary, project directory, or installed Debian package as input
2. Recursively resolving every runtime dependency
3. Downloading all dependency `.deb` files
4. Bundling everything into a single fat `.deb`

The output is a self-contained package. Transfer it to any offline Ubuntu machine. Run `sudo dpkg -i`. Done.

**This is not Docker. This is not a container.** The output installs natively using `dpkg` — no container runtime, no extra tooling, nothing beyond what ships with stock Ubuntu.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     USER INPUT                          │
│   --binary /usr/bin/curl                                │
│   --project ./myproject                                 │
│   --package nginx                                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                     main.py (CLI)                       │
│   Parses args → detects input type → orchestrates flow  │
└──────┬──────────┬──────────────┬──────────────┬─────────┘
       │          │              │              │
       ▼          ▼              ▼              ▼
  analyzer.py  resolver.py  downloader.py  builder.py
  (ldd +       (apt-cache   (apt-get       (dpkg-deb
   dpkg -S)     depends)     download)      --build)
       │          │              │              │
       ▼          ▼              ▼              ▼
  .so paths   full dep       staging/       final
  → package   tree           deps/*.deb     .deb
    names     (deduplicated)
```

### Final `.deb` Internal Structure

```
<name>-airgap.deb
├── DEBIAN/
│   ├── control       ← package metadata (name, version, arch, description)
│   └── postinst      ← runs on target after install
└── opt/airgap/<name>/
    ├── deps/         ← all dependency .deb files
    └── payload/      ← the main binary
```

On `dpkg -i`, the `postinst` script installs all bundled `.deb` files via `dpkg -i deps/*.deb`, then copies the payload binary to `/usr/local/bin/`.

---

## Components

### `main.py` — CLI Entrypoint

Orchestrates the full pipeline. Handles three input types:

- `--binary`: resolves shell wrappers to the real ELF binary, validates with magic byte check (`\x7fELF`)
- `--project`: walks the directory tree to find the main ELF executable
- `--package`: uses `dpkg -L` to find the installed package's binary

Runs all 5 steps in sequence: analyze → resolve → download → prepare payload → build.

### `analyzer.py` — Dependency Analyzer

Runs `ldd` on the binary to list all shared library (`.so`) dependencies. For each `.so` path, runs `dpkg -S` to find the owning Debian package name.

- Skips kernel virtual DSOs (`linux-vdso.so.1`, `linux-gate.so.1`)
- Detects static binaries (`ldd` returns "not a dynamic executable") and skips dep resolution
- Strips architecture qualifiers from package names (e.g. `libc6:amd64` → `libc6`)

System calls used: `ldd`, `dpkg -S`

### `resolver.py` — Recursive Dependency Resolver

Takes the seed package set from the analyzer and expands it into the full dependency tree using BFS. Calls `apt-cache depends` on each package and recursively processes its `Depends` and `PreDepends`.

- Tracks visited packages to handle circular dependencies
- Skips virtual packages (lines starting with `<`)
- Skips meta/base packages that cannot or should not be downloaded (`dpkg`, `debconf`, `base-files`)
- Strips `--recommends`, `--suggests`, `--conflicts`, `--enhances` — only hard deps

System calls used: `apt-cache depends`

### `downloader.py` — Package Downloader

Downloads `.deb` files for all resolved packages into `staging/deps/`. Falls back to architecture-qualified download (`pkg:amd64`) if the initial download fails. Reports per-package success/failure.

System calls used: `apt-get download`

### `builder.py` — `.deb` Builder

Assembles the final directory structure under `staging/build/`, writes the `DEBIAN/control` and `DEBIAN/postinst` files from templates, then calls `dpkg-deb --build` to produce the final `.deb`.

- Calculates `Installed-Size` from actual staged file sizes
- Sets `postinst` as executable (`chmod 755`)
- Uses `\n` line endings in control files (required by `dpkg-deb`)

System calls used: `dpkg-deb --build`

### `templates/control` — Package Metadata Template

Standard Debian control file. Fields populated at build time: `Package`, `Version`, `Installed-Size`, `Description`. Architecture hardcoded to `amd64`.

### `templates/postinst` — Post-Install Script

Bash script executed by `dpkg` on the target machine after package installation. Installs all `.deb` files from `/opt/airgap/<name>/deps/` using `dpkg -i`, then copies the payload binary to `/usr/local/bin/`.

---

## Requirements

Build machine (where `airgap-packager` runs):

- Ubuntu/Debian Linux
- Python 3.6+
- `ldd` (part of `libc-bin`, installed by default)
- `dpkg`, `dpkg-deb` (installed by default)
- `apt-get`, `apt-cache` (installed by default)
- Internet access (to download dependency `.deb` files)
- `sudo` or root not required for most operations; `apt-get download` runs as regular user

Target machine (air-gapped, where the output `.deb` is installed):

- Ubuntu/Debian Linux (matching architecture: `amd64`)
- `dpkg` (installed by default on all Ubuntu/Debian systems)
- No internet required
- `sudo dpkg -i` requires root

---

## Installation

```bash
git clone https://github.com/parinarora/airgap-packager.git
cd airgap-packager
```

No pip dependencies. Runs on Python 3.6+ stdlib only.

---

## Usage

### Package a binary

```bash
python3 main.py --binary /usr/bin/curl -o curl-airgap.deb
```

### Package a project directory

```bash
python3 main.py --project ./myproject -o myproject-airgap.deb
```

### Package an installed Debian package

```bash
python3 main.py --package nginx -o nginx-airgap.deb
```

### Full options

```
usage: airgap-packager [-h] (--binary PATH | --project PATH | --package NAME)
                       [-o PATH] [-n NAME] [-v VER] [--description DESC]

options:
  --binary PATH       Path to a dynamically linked ELF binary
  --project PATH      Path to a project directory containing a main binary
  --package NAME      Name of an already-installed Debian package
  -o, --output PATH   Output .deb file path (default: <name>-airgap.deb)
  -n, --name NAME     Package name for the output .deb
  -v, --version VER   Version string (default: 1.0.0)
  --description DESC  Description for the output .deb
```

### Install on air-gapped target

Transfer the `.deb` to the target machine (USB, SCP over LAN, etc.), then:

```bash
sudo dpkg -i curl-airgap.deb
```

---

## Test Cases

### Test 1 — Static Binary (No Dependencies)

Verify the tool correctly detects a static binary and skips dependency resolution.

```bash
# Compile a static binary
gcc -static -o hello hello.c

python3 main.py --binary ./hello -o hello-airgap.deb
```

Expected output:
```
[Step 1/5] Analyzing binary dependencies (ldd + dpkg -S)
    [INFO] Static binary detected. No shared library deps.
    Found 0 shared libraries
    Mapped to 0 packages
```

Expected `.deb` contents: payload only, no deps bundled.

---

### Test 2 — Dynamic Binary (`curl`)

Verify full pipeline works on a real binary with multiple shared library dependencies.

```bash
python3 main.py --binary /usr/bin/curl -o curl-airgap.deb
```

Expected behavior:
- `ldd` detects `libcurl.so`, `libssl.so`, `libz.so`, `libc.so`, etc.
- `dpkg -S` maps them to packages: `libcurl4`, `libssl3`, `zlib1g`, `libc6`, etc.
- Recursive resolution expands to ~15–30 packages
- All `.deb` files downloaded to `staging/deps/`
- Final `.deb` produced

Verify the output:
```bash
dpkg-deb --contents curl-airgap.deb   # lists all files inside
dpkg-deb --info curl-airgap.deb       # shows control metadata
```

---

### Test 3 — Installed Package (`nginx`)

```bash
# Ensure nginx is installed first
sudo apt install nginx -y

python3 main.py --package nginx -o nginx-airgap.deb
```

Expected behavior:
- `dpkg -L nginx` identifies `/usr/sbin/nginx` as the main binary
- Full dep tree resolved and downloaded
- Fat `.deb` produced

---

### Test 4 — Air-Gap Installation on Clean VM

The real test. Take a fresh Ubuntu VM with no internet (disable network adapter).

```bash
# On build machine
python3 main.py --binary /usr/bin/curl -o curl-airgap.deb

# Transfer to air-gapped VM (USB / shared folder / LAN SCP)
# On air-gapped VM
sudo dpkg -i curl-airgap.deb
curl --version   # must work
```

---

### Test 5 — Project Directory Input

```bash
# Clone a small C project with dependencies
git clone https://github.com/example/small-c-project.git
cd small-c-project && make
cd ..

python3 main.py --project ./small-c-project -o project-airgap.deb
```

Expected behavior:
- Tool walks directory, finds ELF binary
- Runs full pipeline on detected binary

---

### Test 6 — Shell Wrapper Edge Case

Some system binaries (e.g. `python3`) are shell scripts that wrap the real ELF binary.

```bash
python3 main.py --binary /usr/bin/python3
```

Expected behavior:
```
[INFO] /usr/bin/python3 is not an ELF binary (likely a shell wrapper)
[INFO] Searching for real ELF binary for 'python3'...
[INFO] Found real binary: /usr/lib/python3.X/python3.X
```

---

## Known Limitations

- **Architecture**: hardcoded to `amd64`. Does not cross-compile or handle `arm64` targets.
- **Python/pip projects**: only handles ELF binaries and their shared library deps. Pure Python packages with pip dependencies require a separate bundling strategy.
- **Pre/post-install scripts of deps**: bundled dependency `.deb` files may have their own `postinst` scripts that expect internet access (e.g. to download additional data). These may fail on air-gapped targets.
- **Kernel version mismatches**: if the build machine kernel differs significantly from the target, some kernel-linked `.so` files may mismatch.
- **Virtual packages**: packages listed as virtual in `apt-cache` output (e.g. `<mail-transport-agent>`) are skipped. Their real providers may not be included.
- **`apt-get install -f`** in `postinst`: called as a fallback to fix broken deps. Will fail silently on a true air-gapped system with no apt mirror. This is acceptable — if all deps are correctly bundled, `-f` is not needed.

---

## Project Structure

```
airgap-packager/
├── main.py           ← CLI entrypoint and pipeline orchestrator
├── analyzer.py       ← ldd + dpkg -S: finds shared lib deps
├── resolver.py       ← apt-cache depends: recursive dep tree
├── downloader.py     ← apt-get download: fetches .deb files
├── builder.py        ← dpkg-deb --build: assembles final .deb
├── templates/
│   ├── control       ← Debian control file template
│   └── postinst      ← Post-install script template
├── .gitignore
├── LICENSE
└── README.md
```

