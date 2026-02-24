# Complex Playground Design - 50 Container Dependency Graph

## Overview

This document describes a complex Docker container dependency structure with 50 containers organized into 8 regions. The design showcases multiple dependency patterns including linear chains, diamond dependencies, cross-platform mixing, bind mounts, and multi-source COPY operations.

## Dependency Patterns Used

| Pattern | Description | Example |
|---------|-------------|---------|
| **Linear Chain** | Sequential A→B→C dependencies | Region A, Region E |
| **Diamond Pattern** | Multiple paths converging | Region B (B03,B04→B07) |
| **Wide Branch** | One base with many children | Region F (A05→F01,F02,F03) |
| **Cross-Platform** | Mixing stages from different distros | Region D |
| **Bind Mount** | `--mount=type=bind,from=` | Region G |
| **Multi-Source COPY** | `COPY --from=` multiple sources | Region H |
| **Deep Chain** | 8+ level dependencies | Region E |

## Container Regions

### Region A: Fedora Core Foundation (5 containers)
**Base Image:** `fedora:43`
**Purpose:** Primary foundation track with linear chain

```
A01 (fedora:43)
 └── A02
      └── A03
           └── A04
                └── A05
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| A01 | `a01-base` | fedora:43 | Base image with workdir |
| A02 | `a02-tools` | A01 | Install build tools |
| A03 | `a03-python` | A02 | Add Python runtime |
| A04 | `a04-deps` | A03 | Install dependencies |
| A05 | `a05-ready` | A04 | Production-ready base |

---

### Region B: Ubuntu Diamond Pattern (8 containers)
**Base Image:** `ubuntu:24.04`
**Purpose:** Diamond dependency pattern demonstration

```
B01 (ubuntu:24.04)
 └── B02
      ├── B03 ─────┐
      │    └── B05 ├──→ B07
      └── B04 ─────┘     └── B08
           └── B06 ──────────┘
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| B01 | `b01-ubuntu-base` | ubuntu:24.04 | Ubuntu base |
| B02 | `b02-core` | B01 | Core utilities |
| B03 | `b03-dev-tools` | B02 | Development tools branch |
| B04 | `b04-runtime` | B02 | Runtime branch |
| B05 | `b05-compiler` | B03 | Compiler chain |
| B06 | `b06-server` | B04 | Server components |
| B07 | `b07-merge` | B05 + COPY from B06 | Diamond merge point |
| B08 | `b08-final` | B07 | Final Ubuntu build |

---

### Region C: Alpine Lightweight Track (6 containers)
**Base Image:** `alpine:3.19`
**Purpose:** Minimal footprint chain with parallel branches

```
C01 (alpine:3.19)
 ├── C02
 │    └── C03 ──────┐
 │                  ├──→ C05
 └── C04 ───────────┘     └── C06
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| C01 | `c01-alpine-base` | alpine:3.19 | Alpine base |
| C02 | `c02-apk-tools` | C01 | Package manager setup |
| C03 | `c03-build-env` | C02 | Build environment |
| C04 | `c04-minimal` | C01 | Minimal runtime branch |
| C05 | `c05-combined` | C03 + COPY from C04 | Combined artifacts |
| C06 | `c06-alpine-final` | C05 | Production Alpine image |

---

### Region D: Cross-Platform Bridge (7 containers)
**Base Images:** Mixed (inherits from A, B, C)
**Purpose:** Demonstrate cross-distro dependencies

```
A03 ─────→ D01 ────┐
                   ├──→ D03 ──┐
B03 ─────→ D02 ────┘          ├──→ D05 ──→ D06 ──→ D07
                              │
C03 ─────→ D04 ───────────────┘
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| D01 | `d01-from-fedora` | A03 | Fedora-derived container |
| D02 | `d02-from-ubuntu` | B03 | Ubuntu-derived container |
| D03 | `d03-fedora-ubuntu` | D01 + COPY from D02 | Fed+Ubuntu artifacts |
| D04 | `d04-from-alpine` | C03 | Alpine-derived container |
| D05 | `d05-triple-merge` | D03 + COPY from D04 | Three-platform merge |
| D06 | `d06-integrated` | D05 | Integration layer |
| D07 | `d07-cross-final` | D06 | Cross-platform final |

---

### Region E: Deep Chain Track (8 containers)
**Base Image:** `debian:bookworm`
**Purpose:** Maximum depth linear chain (8 levels)

```
E01 (debian:bookworm)
 └── E02
      └── E03
           └── E04
                └── E05
                     └── E06
                          └── E07
                               └── E08
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| E01 | `e01-debian-base` | debian:bookworm | Debian base |
| E02 | `e02-apt-prep` | E01 | APT preparation |
| E03 | `e03-security` | E02 | Security hardening |
| E04 | `e04-network` | E03 | Network tools |
| E05 | `e05-services` | E04 | Service layer |
| E06 | `e06-app-layer` | E05 | Application layer |
| E07 | `e07-config` | E06 | Configuration layer |
| E08 | `e08-deep-final` | E07 | Deepest chain endpoint |

---

### Region F: Wide Fan-Out Pattern (6 containers)
**Base Image:** Inherits from A05
**Purpose:** Wide branching from single point, then merge

```
          ┌── F01 ──┬────────────────┐
          │         ↓               │
A05 ──────┼── F02 ──→ F05           │
          │                         ↓
          └── F03 ──→ F04 ────────→ F06
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| F01 | `f01-api` | A05 | API service branch |
| F02 | `f02-worker` | A05 | Worker service branch |
| F03 | `f03-scheduler` | A05 | Scheduler branch |
| F04 | `f04-queue` | F03 | Queue processor |
| F05 | `f05-api-worker` | F02 + COPY from F01 | API-Worker merge |
| F06 | `f06-orchestrator` | F04 + COPY from F05 + F01 | Full orchestration |

---

### Region G: Advanced Mount Patterns (5 containers)
**Purpose:** Bind mount and advanced FROM patterns

```
E04 ──→ G01 ──(mount)──→ G02 ────┐
                                 ├──→ G04 ──→ G05
B05 ──────────(mount)──→ G03 ────┘
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| G01 | `g01-config-store` | E04 | Configuration storage |
| G02 | `g02-mount-test` | fedora:43 + mount from G01 | Bind mount from G01 |
| G03 | `g03-ubuntu-mount` | ubuntu:24.04 + mount from B05 | Bind mount from B05 |
| G04 | `g04-mount-merge` | G02 + COPY from G03 | Mount artifacts merged |
| G05 | `g05-mount-final` | G04 | Final mount-based image |

---

### Region H: Ultimate Integration (5 containers)
**Purpose:** Final convergence of all major tracks

```
D07 ──────→ H01 ────┐
                    │
G05 ──────→ H02 ────┼──→ H04 ──→ H05 (ULTIMATE ENDPOINT)
                    │     ↑
E08 ──────→ H03 ────┘─────┘
```

| Container | Stage Name | Dependencies | Description |
|-----------|------------|--------------|-------------|
| H01 | `h01-cross-input` | D07 | Cross-platform input |
| H02 | `h02-mount-input` | G05 | Mount pattern input |
| H03 | `h03-deep-input` | E08 | Deep chain input |
| H04 | `h04-mega-merge` | H01 + COPY from H02 + H03 | Mega merge point |
| H05 | `h05-ultimate` | H04 | Ultimate final container |

---

## Visual Dependency Graph (ASCII)

```
                                    FEDORA TRACK                         DEBIAN TRACK
                                  ┌───────────────┐                    ┌────────────────┐
                                  │ A01 (fedora)  │                    │ E01 (debian)   │
                                  └───────┬───────┘                    └───────┬────────┘
                                          ↓                                    ↓
                                  ┌───────┴───────┐                    ┌───────┴────────┐
                                  │     A02       │                    │      E02       │
                                  └───────┬───────┘                    └───────┬────────┘
                                          ↓                                    ↓
    UBUNTU TRACK                  ┌───────┴───────┐                    ┌───────┴────────┐
  ┌─────────────┐                 │     A03       │────┐               │      E03       │
  │ B01 (ubuntu)│                 └───────┬───────┘    │               └───────┬────────┘
  └──────┬──────┘                         ↓            │                       ↓
         ↓                        ┌───────┴───────┐    │               ┌───────┴────────┐
  ┌──────┴──────┐                 │     A04       │    │               │      E04       │───────┐
  │     B02     │                 └───────┬───────┘    │               └───────┬────────┘       │
  └──────┬──────┘                         ↓            │                       ↓               G01
    ┌────┴─────┐                  ┌───────┴───────┐    │               ┌───────┴────────┐       │
    ↓          ↓                  │     A05       │    │               │      E05       │       ↓
┌───┴───┐  ┌───┴───┐              └───────┬───────┘    │               └───────┬────────┘      G02
│  B03  │  │  B04  │               ┌──────┼──────┐     │                       ↓               │
└───┬───┘  └───┬───┘               ↓      ↓      ↓     │               ┌───────┴────────┐      │
    │          │                  F01    F02    F03    │               │      E06       │      │
    ↓          ↓                   │      │      │     │               └───────┬────────┘      │
┌───┴───┐  ┌───┴───┐               ↓      ↓      ↓     │                       ↓               │
│  B05  │  │  B06  │              F05 ←──┘      F04    │               ┌───────┴────────┐      │
└───┬───┘  └───┬───┘               │            │      │               │      E07       │      │
    │          │                   ↓            ↓      │               └───────┬────────┘      │
    │          │              ┌───F06←─────────┘       │                       ↓               │
    │          │              │                        │               ┌───────┴────────┐      │
    ↓          ↓              │    CROSS-PLATFORM      │               │      E08       │      │
  ┌─┴──────────┴──┐           │  ┌─────────────────┐   │               └───────┬────────┘      │
  │      B07      │           │  │ D01 ←───────────┼───┘                       │               │
  └───────┬───────┘           │  └──────┬──────────┘                           │               │
          ↓                   │         ↓                                      │               │
  ┌───────┴───────┐           │  ┌──────┴────┐     ALPINE TRACK               │               │
  │      B08      │           │  │    D02    │←───┐ ┌───────────┐              │               │
  └───────┬───────┘           │  └──────┬────┘    │ │C01 (alpine)              │               │
          │                   │         ↓         │ └─────┬─────┘              │               │
          │                   │  ┌──────┴────┐────┘    ┌──┴──┐                 ↓               │
          └─────────────G03←──┼──│    D03    │         ↓     ↓                H03             │
                         │    │  └──────┬────┘        C02   C04                │               │
                         ↓    │         ↓              │     │                 │               │
                        G04   │  ┌──────┴────┐         ↓     │                 │               │
                         │    │  │    D04    │←──C03 ──┴─→ C05                 │               │
                         ↓    │  └──────┬────┘              │                  │               │
                        G05   │         ↓                   ↓                  │               │
                         │    │  ┌──────┴────┐             C06                 │               │
                         │    │  │    D05    │                                 │               │
                         │    │  └──────┬────┘                                 │               │
                         │    │         ↓                                      │               │
                         │    │  ┌──────┴────┐                                 │               │
                         │    │  │    D06    │                                 │               │
                         │    │  └──────┬────┘                                 │               │
                         │    │         ↓                                      │               │
                         │    │  ┌──────┴────┐                                 │               │
                         │    └─→│    D07    │                                 │               │
                         │       └──────┬────┘                                 │               │
                         │              ↓                                      │               │
                         │       ┌──────┴────┐                                 │               │
                         │       │    H01    │                                 │               │
                         │       └──────┬────┘                                 │               │
                         │              │                                      │               │
                         │              ↓                                      ↓               │
                         └─────→ H02 ──→ H04 ←──────────────────────────────────┘←──────────────┘
                                         │
                                         ↓
                                 ┌───────┴───────┐
                                 │     H05       │
                                 │  (ULTIMATE)   │
                                 └───────────────┘
```

## Statistics Summary

| Metric | Value |
|--------|-------|
| **Total Containers** | 50 |
| **Base Images** | 4 (fedora:43, ubuntu:24.04, alpine:3.19, debian:bookworm) |
| **Maximum Depth** | 15 levels (A01→A02→A03→A04→A05→F01→F06 or E01→...→E08→H03→H04→H05) |
| **Diamond Merges** | 3 (B07, F06, H04) |
| **Cross-Platform Merges** | 4 (D03, D05, G04, H04) |
| **Bind Mount Uses** | 3 (G02, G03, H region mounts) |
| **COPY --from Operations** | 12 |
| **Parallel Branches** | 7 |
| **Convergence Points** | 6 |

## Directory Structure

```
playground/
├── region_A/
│   └── fedora_core/
│       ├── A01_base/
│       ├── A02_tools/
│       ├── A03_python/
│       ├── A04_deps/
│       └── A05_ready/
├── region_B/
│   └── ubuntu_diamond/
│       ├── B01_ubuntu_base/
│       ├── B02_core/
│       ├── B03_dev_tools/
│       ├── B04_runtime/
│       ├── B05_compiler/
│       ├── B06_server/
│       ├── B07_merge/
│       └── B08_final/
├── region_C/
│   └── alpine_track/
│       ├── C01_alpine_base/
│       ├── C02_apk_tools/
│       ├── C03_build_env/
│       ├── C04_minimal/
│       ├── C05_combined/
│       └── C06_alpine_final/
├── region_D/
│   └── cross_platform/
│       ├── D01_from_fedora/
│       ├── D02_from_ubuntu/
│       ├── D03_fedora_ubuntu/
│       ├── D04_from_alpine/
│       ├── D05_triple_merge/
│       ├── D06_integrated/
│       └── D07_cross_final/
├── region_E/
│   └── debian_deep/
│       ├── E01_debian_base/
│       ├── E02_apt_prep/
│       ├── E03_security/
│       ├── E04_network/
│       ├── E05_services/
│       ├── E06_app_layer/
│       ├── E07_config/
│       └── E08_deep_final/
├── region_F/
│   └── fan_out/
│       ├── F01_api/
│       ├── F02_worker/
│       ├── F03_scheduler/
│       ├── F04_queue/
│       ├── F05_api_worker/
│       └── F06_orchestrator/
├── region_G/
│   └── mount_patterns/
│       ├── G01_config_store/
│       ├── G02_mount_test/
│       ├── G03_ubuntu_mount/
│       ├── G04_mount_merge/
│       └── G05_mount_final/
└── region_H/
    └── integration/
        ├── H01_cross_input/
        ├── H02_mount_input/
        ├── H03_deep_input/
        ├── H04_mega_merge/
        └── H05_ultimate/
```

## Usage

Run the complex playground setup:

```bash
python setupComplexPlayground.py
```

Clean up:

```bash
python setupComplexPlayground.py --clean
```
