#!/usr/bin/env python3
"""
Complex Playground Setup Script
Creates a 50-container Docker playground with complex dependency chains.

Dependency patterns demonstrated:
- Linear chains (A, E)
- Diamond patterns (B, F)
- Cross-platform mixing (D)
- Bind mount patterns (G, H)
- Wide fan-out (F)
- Deep chains up to 8+ levels (E)

See COMPLEX_PLAYGROUND_DESIGN.md for full documentation.
"""

import os
import shutil
from pathlib import Path
import argparse


# =============================================================================
# DOCKERFILE TEMPLATES
# =============================================================================

DOCKERFILE_TEMPLATES = {
    # -------------------------------------------------------------------------
    # REGION A: Fedora Core Foundation (5 containers)
    # -------------------------------------------------------------------------
    "A01": """# Region A: Fedora Core Foundation
# A01 - Base image with workdir setup
# Dependencies: fedora:43 (external)

FROM fedora:43 AS a01-base
LABEL region="A" container="A01" description="Fedora base image"
WORKDIR /app
RUN touch a01-base.txt
RUN echo "A01 base initialized" > /app/a01.log
""",

    "A02": """# Region A: Fedora Core Foundation
# A02 - Build tools layer (simulated)
# Dependencies: A01

FROM a01-base:prebake AS a02-tools
LABEL region="A" container="A02" description="Build tools layer"
RUN mkdir -p /app/tools && echo "gcc make cmake git" > /app/tools/installed.txt
RUN touch a02-tools.txt
RUN echo "A02 tools installed" >> /app/a01.log
""",

    "A03": """# Region A: Fedora Core Foundation
# A03 - Python runtime layer (simulated)
# Dependencies: A02

FROM a02-tools:prebake AS a03-python
LABEL region="A" container="A03" description="Python runtime layer"
RUN mkdir -p /app/python && echo "python3 pip virtualenv" > /app/python/installed.txt
RUN touch a03-python.txt
RUN echo "A03 python added" >> /app/a01.log
""",

    "A04": """# Region A: Fedora Core Foundation
# A04 - Dependencies layer (simulated)
# Dependencies: A03

FROM a03-python:prebake AS a04-deps
LABEL region="A" container="A04" description="Dependencies layer"
RUN mkdir -p /app/deps && echo "flask requests redis celery" > /app/deps/installed.txt
RUN touch a04-deps.txt
RUN echo "A04 deps installed" >> /app/a01.log
""",

    "A05": """# Region A: Fedora Core Foundation
# A05 - Production-ready base (simulated)
# Dependencies: A04

FROM a04-deps:prebake AS a05-ready
LABEL region="A" container="A05" description="Production-ready Fedora base"
RUN mkdir -p /app/supervisor && echo "supervisor configured" > /app/supervisor/config.txt
RUN touch a05-ready.txt
RUN echo "A05 ready for production" >> /app/a01.log
EXPOSE 5000
""",

    # -------------------------------------------------------------------------
    # REGION B: Ubuntu Diamond Pattern (8 containers)
    # -------------------------------------------------------------------------
    "B01": """# Region B: Ubuntu Diamond Pattern
# B01 - Ubuntu base image
# Dependencies: ubuntu:24.04 (external)

FROM ubuntu:24.04 AS b01-ubuntu-base
LABEL region="B" container="B01" description="Ubuntu base image"
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir -p /app/certs && echo "ca-certificates configured" > /app/certs/status.txt
RUN touch b01-ubuntu-base.txt
RUN echo "B01 ubuntu base" > /app/b01.log
""",

    "B02": """# Region B: Ubuntu Diamond Pattern
# B02 - Core utilities (simulated)
# Dependencies: B01

FROM b01-ubuntu-base:prebake AS b02-core
LABEL region="B" container="B02" description="Core utilities layer"
RUN mkdir -p /app/utils && echo "curl wget vim" > /app/utils/installed.txt
RUN touch b02-core.txt
RUN echo "B02 core utilities" >> /app/b01.log
""",

    "B03": """# Region B: Ubuntu Diamond Pattern
# B03 - Development tools branch (LEFT side of diamond)
# Dependencies: B02

FROM b02-core:prebake AS b03-dev-tools
LABEL region="B" container="B03" description="Development tools branch"
RUN mkdir -p /app/devtools && echo "build-essential git" > /app/devtools/installed.txt
RUN touch b03-dev-tools.txt
RUN echo "B03 dev tools" >> /app/b01.log
""",

    "B04": """# Region B: Ubuntu Diamond Pattern
# B04 - Runtime branch (RIGHT side of diamond)
# Dependencies: B02

FROM b02-core:prebake AS b04-runtime
LABEL region="B" container="B04" description="Runtime branch"
RUN mkdir -p /app/runtime && echo "python3 pip" > /app/runtime/installed.txt
RUN touch b04-runtime.txt
RUN echo "B04 runtime" >> /app/b01.log
""",

    "B05": """# Region B: Ubuntu Diamond Pattern
# B05 - Compiler chain (extends B03)
# Dependencies: B03

FROM b03-dev-tools:prebake AS b05-compiler
LABEL region="B" container="B05" description="Compiler chain"
RUN mkdir -p /app/compiler && echo "clang llvm" > /app/compiler/installed.txt
RUN touch b05-compiler.txt
RUN echo "B05 compiler" >> /app/b01.log
""",

    "B06": """# Region B: Ubuntu Diamond Pattern
# B06 - Server components (extends B04)
# Dependencies: B04

FROM b04-runtime:prebake AS b06-server
LABEL region="B" container="B06" description="Server components"
RUN mkdir -p /app/server && echo "nginx supervisor" > /app/server/installed.txt
RUN mkdir -p /var/log/supervisor
RUN touch b06-server.txt
RUN echo "B06 server" >> /app/b01.log
""",

    "B07": """# Region B: Ubuntu Diamond Pattern
# B07 - Diamond merge point (merges B05 and B06)
# Dependencies: B05, COPY from B06
# Pattern: DIAMOND MERGE

FROM b05-compiler:prebake AS b07-merge
LABEL region="B" container="B07" description="Diamond merge point"
COPY --from=b06-server:prebake /var/log/supervisor /var/log/supervisor
COPY --from=b06-server:prebake /app/b06-server.txt /app/
RUN touch b07-merge.txt
RUN echo "B07 diamond merged" >> /app/b01.log
""",

    "B08": """# Region B: Ubuntu Diamond Pattern
# B08 - Final Ubuntu build
# Dependencies: B07

FROM b07-merge:prebake AS b08-final
LABEL region="B" container="B08" description="Final Ubuntu build"
WORKDIR /app
RUN touch b08-final.txt
RUN echo "B08 final" >> /app/b01.log
EXPOSE 8080
CMD ["sleep", "infinity"]
""",

    # -------------------------------------------------------------------------
    # REGION C: Alpine Lightweight Track (6 containers)
    # -------------------------------------------------------------------------
    "C01": """# Region C: Alpine Lightweight Track
# C01 - Alpine base image
# Dependencies: alpine:3.19 (external)

FROM alpine:3.19 AS c01-alpine-base
LABEL region="C" container="C01" description="Alpine base image"
WORKDIR /app
RUN mkdir -p /app/shell && echo "bash configured" > /app/shell/status.txt
RUN touch c01-alpine-base.txt
RUN echo "C01 alpine base" > /app/c01.log
""",

    "C02": """# Region C: Alpine Lightweight Track
# C02 - Package manager setup (simulated)
# Dependencies: C01

FROM c01-alpine-base:prebake AS c02-apk-tools
LABEL region="C" container="C02" description="Package manager setup"
RUN mkdir -p /app/tools && echo "curl wget" > /app/tools/installed.txt
RUN touch c02-apk-tools.txt
RUN echo "C02 apk tools" >> /app/c01.log
""",

    "C03": """# Region C: Alpine Lightweight Track
# C03 - Build environment (simulated)
# Dependencies: C02

FROM c02-apk-tools:prebake AS c03-build-env
LABEL region="C" container="C03" description="Build environment"
RUN mkdir -p /app/build && echo "build-base python3 pip" > /app/build/installed.txt
RUN touch c03-build-env.txt
RUN echo "C03 build env" >> /app/c01.log
""",

    "C04": """# Region C: Alpine Lightweight Track
# C04 - Minimal runtime branch (parallel to C02-C03)
# Dependencies: C01

FROM c01-alpine-base:prebake AS c04-minimal
LABEL region="C" container="C04" description="Minimal runtime branch"
RUN mkdir -p /app/minimal && echo "python3 minimal" > /app/minimal/installed.txt
RUN touch c04-minimal.txt
RUN echo "C04 minimal runtime" >> /app/c01.log
""",

    "C05": """# Region C: Alpine Lightweight Track
# C05 - Combined artifacts (merges C03 and C04)
# Dependencies: C03, COPY from C04
# Pattern: PARALLEL BRANCH MERGE

FROM c03-build-env:prebake AS c05-combined
LABEL region="C" container="C05" description="Combined artifacts"
COPY --from=c04-minimal:prebake /app/c04-minimal.txt /app/
RUN touch c05-combined.txt
RUN echo "C05 combined" >> /app/c01.log
""",

    "C06": """# Region C: Alpine Lightweight Track
# C06 - Production Alpine image
# Dependencies: C05

FROM c05-combined:prebake AS c06-alpine-final
LABEL region="C" container="C06" description="Production Alpine image"
RUN touch c06-alpine-final.txt
RUN echo "C06 final" >> /app/c01.log
EXPOSE 3000
CMD ["sleep", "infinity"]
""",

    # -------------------------------------------------------------------------
    # REGION D: Cross-Platform Bridge (7 containers)
    # -------------------------------------------------------------------------
    "D01": """# Region D: Cross-Platform Bridge
# D01 - Fedora-derived container
# Dependencies: A03 (Fedora Python layer)
# Pattern: CROSS-PLATFORM FROM

FROM a03-python:prebake AS d01-from-fedora
LABEL region="D" container="D01" description="Fedora-derived container"
WORKDIR /app/cross
RUN touch d01-from-fedora.txt
RUN echo "D01 from fedora" > /app/cross/d01.log
""",

    "D02": """# Region D: Cross-Platform Bridge
# D02 - Ubuntu-derived container
# Dependencies: B03 (Ubuntu dev-tools)
# Pattern: CROSS-PLATFORM FROM

FROM b03-dev-tools:prebake AS d02-from-ubuntu
LABEL region="D" container="D02" description="Ubuntu-derived container"
WORKDIR /app/cross
RUN touch d02-from-ubuntu.txt
RUN echo "D02 from ubuntu" > /app/cross/d02.log
""",

    "D03": """# Region D: Cross-Platform Bridge
# D03 - Fedora+Ubuntu artifacts merge
# Dependencies: D01, COPY from D02
# Pattern: CROSS-PLATFORM ARTIFACT MERGE

FROM d01-from-fedora:prebake AS d03-fedora-ubuntu
LABEL region="D" container="D03" description="Fedora+Ubuntu artifacts"
COPY --from=d02-from-ubuntu:prebake /app/cross/d02-from-ubuntu.txt /app/cross/
COPY --from=d02-from-ubuntu:prebake /app/cross/d02.log /app/cross/d02.log
RUN touch d03-fedora-ubuntu.txt
RUN echo "D03 fedora+ubuntu merge" >> /app/cross/d01.log
""",

    "D04": """# Region D: Cross-Platform Bridge
# D04 - Alpine-derived container
# Dependencies: C03 (Alpine build-env)
# Pattern: CROSS-PLATFORM FROM

FROM c03-build-env:prebake AS d04-from-alpine
LABEL region="D" container="D04" description="Alpine-derived container"
WORKDIR /app/cross
COPY --from=c03-build-env:prebake /app/c03-build-env.txt /app/cross/
RUN touch d04-from-alpine.txt
RUN echo "D04 from alpine" > /app/cross/d04.log
""",

    "D05": """# Region D: Cross-Platform Bridge
# D05 - Triple platform merge (Fedora+Ubuntu+Alpine)
# Dependencies: D03, COPY from D04
# Pattern: TRIPLE CROSS-PLATFORM MERGE

FROM d03-fedora-ubuntu:prebake AS d05-triple-merge
LABEL region="D" container="D05" description="Triple platform merge"
COPY --from=d04-from-alpine:prebake /app/cross/d04-from-alpine.txt /app/cross/
COPY --from=d04-from-alpine:prebake /app/cross/d04.log /app/cross/d04.log
RUN touch d05-triple-merge.txt
RUN echo "D05 triple merge (fedora+ubuntu+alpine)" >> /app/cross/d01.log
""",

    "D06": """# Region D: Cross-Platform Bridge
# D06 - Integration layer
# Dependencies: D05

FROM d05-triple-merge:prebake AS d06-integrated
LABEL region="D" container="D06" description="Integration layer"
RUN touch d06-integrated.txt
RUN echo "D06 integrated" >> /app/cross/d01.log
""",

    "D07": """# Region D: Cross-Platform Bridge
# D07 - Cross-platform final
# Dependencies: D06

FROM d06-integrated:prebake AS d07-cross-final
LABEL region="D" container="D07" description="Cross-platform final"
RUN touch d07-cross-final.txt
RUN echo "D07 cross-platform final" >> /app/cross/d01.log
EXPOSE 4000
""",

    # -------------------------------------------------------------------------
    # REGION E: Deep Chain Track (8 containers) - Maximum depth
    # -------------------------------------------------------------------------
    "E01": """# Region E: Deep Chain Track (8 levels)
# E01 - Debian base image
# Dependencies: debian:bookworm (external)
# DEPTH: 1

FROM debian:bookworm AS e01-debian-base
LABEL region="E" container="E01" description="Debian base" depth="1"
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir -p /app/certs && echo "ca-certificates configured" > /app/certs/status.txt
RUN touch e01-debian-base.txt
RUN echo "E01 debian base [depth=1]" > /app/depth.log
""",

    "E02": """# Region E: Deep Chain Track (8 levels)
# E02 - APT preparation (simulated)
# Dependencies: E01
# DEPTH: 2

FROM e01-debian-base:prebake AS e02-apt-prep
LABEL region="E" container="E02" description="APT preparation" depth="2"
RUN mkdir -p /app/apt && echo "apt-utils configured" > /app/apt/status.txt
RUN touch e02-apt-prep.txt
RUN echo "E02 apt prep [depth=2]" >> /app/depth.log
""",

    "E03": """# Region E: Deep Chain Track (8 levels)
# E03 - Security hardening (simulated)
# Dependencies: E02
# DEPTH: 3

FROM e02-apt-prep:prebake AS e03-security
LABEL region="E" container="E03" description="Security hardening" depth="3"
RUN mkdir -p /app/security && echo "fail2ban ufw configured" > /app/security/status.txt
RUN touch e03-security.txt
RUN echo "E03 security [depth=3]" >> /app/depth.log
""",

    "E04": """# Region E: Deep Chain Track (8 levels)
# E04 - Network tools (simulated)
# Dependencies: E03
# DEPTH: 4

FROM e03-security:prebake AS e04-network
LABEL region="E" container="E04" description="Network tools" depth="4"
RUN mkdir -p /app/network && echo "curl wget net-tools" > /app/network/installed.txt
RUN touch e04-network.txt
RUN echo "E04 network [depth=4]" >> /app/depth.log
""",

    "E05": """# Region E: Deep Chain Track (8 levels)
# E05 - Service layer (simulated)
# Dependencies: E04
# DEPTH: 5

FROM e04-network:prebake AS e05-services
LABEL region="E" container="E05" description="Service layer" depth="5"
RUN mkdir -p /app/services /var/log/supervisor && echo "systemd supervisor" > /app/services/installed.txt
RUN touch e05-services.txt
RUN echo "E05 services [depth=5]" >> /app/depth.log
""",

    "E06": """# Region E: Deep Chain Track (8 levels)
# E06 - Application layer (simulated)
# Dependencies: E05
# DEPTH: 6

FROM e05-services:prebake AS e06-app-layer
LABEL region="E" container="E06" description="Application layer" depth="6"
RUN mkdir -p /app/python && echo "python3 pip" > /app/python/installed.txt
RUN touch e06-app-layer.txt
RUN echo "E06 app layer [depth=6]" >> /app/depth.log
""",

    "E07": """# Region E: Deep Chain Track (8 levels)
# E07 - Configuration layer
# Dependencies: E06
# DEPTH: 7

FROM e06-app-layer:prebake AS e07-config
LABEL region="E" container="E07" description="Configuration layer" depth="7"
RUN mkdir -p /etc/myapp /var/myapp
RUN touch e07-config.txt
RUN echo "E07 config [depth=7]" >> /app/depth.log
""",

    "E08": """# Region E: Deep Chain Track (8 levels)
# E08 - Deepest chain endpoint
# Dependencies: E07
# DEPTH: 8 (MAXIMUM DEPTH IN THIS REGION)

FROM e07-config:prebake AS e08-deep-final
LABEL region="E" container="E08" description="Deepest chain endpoint" depth="8"
WORKDIR /app
RUN touch e08-deep-final.txt
RUN echo "E08 deep final [depth=8] - END OF DEEP CHAIN" >> /app/depth.log
EXPOSE 8888
CMD ["sleep", "infinity"]
""",

    # -------------------------------------------------------------------------
    # REGION F: Wide Fan-Out Pattern (6 containers)
    # -------------------------------------------------------------------------
    "F01": """# Region F: Wide Fan-Out Pattern
# F01 - API service branch
# Dependencies: A05 (Fedora production-ready)
# Pattern: WIDE BRANCH (1 of 3)

FROM a05-ready:prebake AS f01-api
LABEL region="F" container="F01" description="API service branch"
WORKDIR /app/api
RUN mkdir -p /app/api/routes /app/api/models
RUN touch f01-api.txt
RUN echo "F01 api branch" > /app/api/f01.log
""",

    "F02": """# Region F: Wide Fan-Out Pattern
# F02 - Worker service branch
# Dependencies: A05 (Fedora production-ready)
# Pattern: WIDE BRANCH (2 of 3)

FROM a05-ready:prebake AS f02-worker
LABEL region="F" container="F02" description="Worker service branch"
WORKDIR /app/worker
RUN mkdir -p /app/worker/tasks /app/worker/queues
RUN touch f02-worker.txt
RUN echo "F02 worker branch" > /app/worker/f02.log
""",

    "F03": """# Region F: Wide Fan-Out Pattern
# F03 - Scheduler branch
# Dependencies: A05 (Fedora production-ready)
# Pattern: WIDE BRANCH (3 of 3)

FROM a05-ready:prebake AS f03-scheduler
LABEL region="F" container="F03" description="Scheduler branch"
WORKDIR /app/scheduler
RUN mkdir -p /app/scheduler/jobs /app/scheduler/cron
RUN touch f03-scheduler.txt
RUN echo "F03 scheduler branch" > /app/scheduler/f03.log
""",

    "F04": """# Region F: Wide Fan-Out Pattern
# F04 - Queue processor (extends scheduler)
# Dependencies: F03

FROM f03-scheduler:prebake AS f04-queue
LABEL region="F" container="F04" description="Queue processor"
WORKDIR /app/queue
COPY --from=f03-scheduler:prebake /app/scheduler /app/queue/scheduler
RUN touch f04-queue.txt
RUN echo "F04 queue processor" > /app/queue/f04.log
""",

    "F05": """# Region F: Wide Fan-Out Pattern
# F05 - API-Worker merge
# Dependencies: F02, COPY from F01
# Pattern: PARTIAL FAN-IN

FROM f02-worker:prebake AS f05-api-worker
LABEL region="F" container="F05" description="API-Worker merge"
WORKDIR /app/merged
COPY --from=f01-api:prebake /app/api /app/merged/api
COPY --from=f02-worker:prebake /app/worker /app/merged/worker
RUN touch f05-api-worker.txt
RUN echo "F05 api+worker merged" > /app/merged/f05.log
""",

    "F06": """# Region F: Wide Fan-Out Pattern
# F06 - Full orchestrator (merges F04, F05, and F01)
# Dependencies: F04, COPY from F05, COPY from F01
# Pattern: FULL FAN-IN CONVERGENCE

FROM f04-queue:prebake AS f06-orchestrator
LABEL region="F" container="F06" description="Full orchestrator"
WORKDIR /app/orchestrator
COPY --from=f01-api:prebake /app/api /app/orchestrator/api
COPY --from=f05-api-worker:prebake /app/merged /app/orchestrator/merged
COPY --from=f04-queue:prebake /app/queue /app/orchestrator/queue
RUN touch f06-orchestrator.txt
RUN echo "F06 full orchestrator - ALL BRANCHES MERGED" > /app/orchestrator/f06.log
EXPOSE 9000
""",

    # -------------------------------------------------------------------------
    # REGION G: Advanced Mount Patterns (5 containers)
    # -------------------------------------------------------------------------
    "G01": """# Region G: Advanced Mount Patterns
# G01 - Configuration storage (derived from E04)
# Dependencies: E04 (Debian network layer)

FROM e04-network:prebake AS g01-config-store
LABEL region="G" container="G01" description="Configuration storage"
WORKDIR /config
RUN mkdir -p /config/templates /config/secrets
RUN echo "config-data-from-g01" > /config/store.txt
RUN touch g01-config-store.txt
""",

    "G02": """# Region G: Advanced Mount Patterns
# G02 - Bind mount test (mounts from G01)
# Dependencies: fedora:43 + bind mount from G01
# Pattern: BIND MOUNT DEPENDENCY
# syntax=docker/dockerfile:1.7

FROM fedora:43 AS g02-mount-test
LABEL region="G" container="G02" description="Bind mount test"
WORKDIR /app

# Mount configuration from G01 and copy it
RUN --mount=type=bind,from=g01-config-store:prebake,source=/config/store.txt,target=/tmp/config.txt \\
    cp /tmp/config.txt /app/mounted-config.txt

RUN touch g02-mount-test.txt
RUN echo "G02 mount from G01" > /app/g02.log
""",

    "G03": """# Region G: Advanced Mount Patterns
# G03 - Ubuntu mount (mounts from B05)
# Dependencies: ubuntu:24.04 + bind mount from B05
# Pattern: CROSS-REGION BIND MOUNT
# syntax=docker/dockerfile:1.7

FROM ubuntu:24.04 AS g03-ubuntu-mount
LABEL region="G" container="G03" description="Ubuntu mount"
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Mount artifacts from B05 (Ubuntu compiler chain)
RUN --mount=type=bind,from=b05-compiler:prebake,source=/app/b05-compiler.txt,target=/tmp/b05.txt \\
    cp /tmp/b05.txt /app/mounted-from-b05.txt

RUN touch g03-ubuntu-mount.txt
RUN echo "G03 mount from B05" > /app/g03.log
""",

    "G04": """# Region G: Advanced Mount Patterns
# G04 - Mount artifacts merged
# Dependencies: G02, COPY from G03
# Pattern: MOUNT RESULT MERGE

FROM g02-mount-test:prebake AS g04-mount-merge
LABEL region="G" container="G04" description="Mount artifacts merged"
WORKDIR /app/merged
COPY --from=g03-ubuntu-mount:prebake /app/mounted-from-b05.txt /app/merged/
COPY --from=g03-ubuntu-mount:prebake /app/g03.log /app/merged/
COPY --from=g02-mount-test:prebake /app/mounted-config.txt /app/merged/
RUN touch g04-mount-merge.txt
RUN echo "G04 mount merge" > /app/merged/g04.log
""",

    "G05": """# Region G: Advanced Mount Patterns
# G05 - Final mount-based image
# Dependencies: G04

FROM g04-mount-merge:prebake AS g05-mount-final
LABEL region="G" container="G05" description="Final mount-based image"
WORKDIR /app/final
COPY --from=g04-mount-merge:prebake /app/merged /app/final/merged
RUN touch g05-mount-final.txt
RUN echo "G05 mount final" > /app/final/g05.log
EXPOSE 7000
""",

    # -------------------------------------------------------------------------
    # REGION H: Ultimate Integration (5 containers)
    # -------------------------------------------------------------------------
    "H01": """# Region H: Ultimate Integration
# H01 - Cross-platform input
# Dependencies: D07 (Cross-platform final)

FROM d07-cross-final:prebake AS h01-cross-input
LABEL region="H" container="H01" description="Cross-platform input"
WORKDIR /integration
RUN mkdir -p /integration/cross
COPY --from=d07-cross-final:prebake /app/cross /integration/cross/
RUN touch h01-cross-input.txt
RUN echo "H01 cross input" > /integration/h01.log
""",

    "H02": """# Region H: Ultimate Integration
# H02 - Mount pattern input
# Dependencies: G05 (Mount final)

FROM g05-mount-final:prebake AS h02-mount-input
LABEL region="H" container="H02" description="Mount pattern input"
WORKDIR /integration
RUN mkdir -p /integration/mount
COPY --from=g05-mount-final:prebake /app/final /integration/mount/
RUN touch h02-mount-input.txt
RUN echo "H02 mount input" > /integration/h02.log
""",

    "H03": """# Region H: Ultimate Integration
# H03 - Deep chain input
# Dependencies: E08 (Deepest chain endpoint)

FROM e08-deep-final:prebake AS h03-deep-input
LABEL region="H" container="H03" description="Deep chain input"
WORKDIR /integration
RUN mkdir -p /integration/deep
COPY --from=e08-deep-final:prebake /app /integration/deep/
RUN touch h03-deep-input.txt
RUN echo "H03 deep input" > /integration/h03.log
""",

    "H04": """# Region H: Ultimate Integration
# H04 - Mega merge point (ALL tracks converge)
# Dependencies: H01, COPY from H02, COPY from H03
# Pattern: ULTIMATE CONVERGENCE POINT

FROM h01-cross-input:prebake AS h04-mega-merge
LABEL region="H" container="H04" description="Mega merge point"
WORKDIR /ultimate

# Bring in cross-platform track
COPY --from=h01-cross-input:prebake /integration/cross /ultimate/cross/

# Bring in mount pattern track
COPY --from=h02-mount-input:prebake /integration/mount /ultimate/mount/

# Bring in deep chain track  
COPY --from=h03-deep-input:prebake /integration/deep /ultimate/deep/

RUN touch h04-mega-merge.txt
RUN echo "H04 MEGA MERGE - All tracks converged" > /ultimate/h04.log
RUN echo "Tracks merged: A+B+C+D (cross), E (deep), F (fan-out via A), G (mount)" >> /ultimate/h04.log
""",

    "H05": """# Region H: Ultimate Integration
# H05 - Ultimate final container (END OF ALL CHAINS)
# Dependencies: H04
# This is the final convergence point for ALL 50 containers

FROM h04-mega-merge:prebake AS h05-ultimate
LABEL region="H" container="H05" description="ULTIMATE FINAL CONTAINER"
WORKDIR /ultimate

RUN touch h05-ultimate.txt
RUN echo "============================================" > /ultimate/ULTIMATE.log
RUN echo "H05 - ULTIMATE FINAL CONTAINER" >> /ultimate/ULTIMATE.log
RUN echo "============================================" >> /ultimate/ULTIMATE.log
RUN echo "" >> /ultimate/ULTIMATE.log
RUN echo "This container represents the convergence of:" >> /ultimate/ULTIMATE.log
RUN echo "  - Region A: Fedora Core (5 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region B: Ubuntu Diamond (8 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region C: Alpine Track (6 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region D: Cross-Platform (7 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region E: Deep Chain (8 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region F: Fan-Out Pattern (6 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region G: Mount Patterns (5 containers)" >> /ultimate/ULTIMATE.log
RUN echo "  - Region H: Integration (5 containers)" >> /ultimate/ULTIMATE.log
RUN echo "" >> /ultimate/ULTIMATE.log
RUN echo "Total: 50 containers" >> /ultimate/ULTIMATE.log
RUN echo "Maximum dependency depth: 15+ levels" >> /ultimate/ULTIMATE.log

EXPOSE 80 443 8080 9000
CMD ["sleep", "infinity"]
""",
}


# =============================================================================
# DIRECTORY STRUCTURE
# =============================================================================

DIRECTORY_STRUCTURE = {
    # Region A: Fedora Core Foundation
    "A01": "region_A/fedora_core/A01_base",
    "A02": "region_A/fedora_core/A02_tools",
    "A03": "region_A/fedora_core/A03_python",
    "A04": "region_A/fedora_core/A04_deps",
    "A05": "region_A/fedora_core/A05_ready",
    
    # Region B: Ubuntu Diamond Pattern
    "B01": "region_B/ubuntu_diamond/B01_ubuntu_base",
    "B02": "region_B/ubuntu_diamond/B02_core",
    "B03": "region_B/ubuntu_diamond/B03_dev_tools",
    "B04": "region_B/ubuntu_diamond/B04_runtime",
    "B05": "region_B/ubuntu_diamond/B05_compiler",
    "B06": "region_B/ubuntu_diamond/B06_server",
    "B07": "region_B/ubuntu_diamond/B07_merge",
    "B08": "region_B/ubuntu_diamond/B08_final",
    
    # Region C: Alpine Lightweight Track
    "C01": "region_C/alpine_track/C01_alpine_base",
    "C02": "region_C/alpine_track/C02_apk_tools",
    "C03": "region_C/alpine_track/C03_build_env",
    "C04": "region_C/alpine_track/C04_minimal",
    "C05": "region_C/alpine_track/C05_combined",
    "C06": "region_C/alpine_track/C06_alpine_final",
    
    # Region D: Cross-Platform Bridge
    "D01": "region_D/cross_platform/D01_from_fedora",
    "D02": "region_D/cross_platform/D02_from_ubuntu",
    "D03": "region_D/cross_platform/D03_fedora_ubuntu",
    "D04": "region_D/cross_platform/D04_from_alpine",
    "D05": "region_D/cross_platform/D05_triple_merge",
    "D06": "region_D/cross_platform/D06_integrated",
    "D07": "region_D/cross_platform/D07_cross_final",
    
    # Region E: Deep Chain Track
    "E01": "region_E/debian_deep/E01_debian_base",
    "E02": "region_E/debian_deep/E02_apt_prep",
    "E03": "region_E/debian_deep/E03_security",
    "E04": "region_E/debian_deep/E04_network",
    "E05": "region_E/debian_deep/E05_services",
    "E06": "region_E/debian_deep/E06_app_layer",
    "E07": "region_E/debian_deep/E07_config",
    "E08": "region_E/debian_deep/E08_deep_final",
    
    # Region F: Wide Fan-Out Pattern
    "F01": "region_F/fan_out/F01_api",
    "F02": "region_F/fan_out/F02_worker",
    "F03": "region_F/fan_out/F03_scheduler",
    "F04": "region_F/fan_out/F04_queue",
    "F05": "region_F/fan_out/F05_api_worker",
    "F06": "region_F/fan_out/F06_orchestrator",
    
    # Region G: Advanced Mount Patterns
    "G01": "region_G/mount_patterns/G01_config_store",
    "G02": "region_G/mount_patterns/G02_mount_test",
    "G03": "region_G/mount_patterns/G03_ubuntu_mount",
    "G04": "region_G/mount_patterns/G04_mount_merge",
    "G05": "region_G/mount_patterns/G05_mount_final",
    
    # Region H: Ultimate Integration
    "H01": "region_H/integration/H01_cross_input",
    "H02": "region_H/integration/H02_mount_input",
    "H03": "region_H/integration/H03_deep_input",
    "H04": "region_H/integration/H04_mega_merge",
    "H05": "region_H/integration/H05_ultimate",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ensure_directory_exists(directory_path):
    """Create directory if it doesn't exist"""
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)


def write_dockerfile(content, destination_dir):
    """Write dockerfile content to destination directory"""
    ensure_directory_exists(destination_dir)
    destination_file = os.path.join(destination_dir, "Dockerfile")
    
    with open(destination_file, "w", newline='\n') as f:
        f.write(content)
    
    return destination_file


def create_requirements_file(destination_dir):
    """Create a minimal requirements.txt file"""
    content = """# Auto-generated requirements.txt for complex playground
flask>=2.0.0
requests>=2.25.0
redis>=4.0.0
celery>=5.0.0
"""
    requirements_path = os.path.join(destination_dir, "requirements.txt")
    with open(requirements_path, "w", newline='\n') as f:
        f.write(content)


def create_app_files(destination_dir, container_id):
    """Create sample app files"""
    # app.py
    app_content = f"""# Auto-generated app.py for {container_id}
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return f"Hello from {container_id}!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""
    with open(os.path.join(destination_dir, "app.py"), "w", newline='\n') as f:
        f.write(app_content)
    
    # helloBase.py
    hello_content = f"""# Auto-generated helloBase.py for {container_id}
print("Hello from container {container_id}!")
"""
    with open(os.path.join(destination_dir, "helloBase.py"), "w", newline='\n') as f:
        f.write(hello_content)


def print_statistics():
    """Print playground statistics"""
    regions = {}
    for container_id in DOCKERFILE_TEMPLATES.keys():
        region = container_id[0]
        regions[region] = regions.get(region, 0) + 1
    
    print("\n" + "=" * 60)
    print("COMPLEX PLAYGROUND STATISTICS")
    print("=" * 60)
    print(f"\nTotal containers: {len(DOCKERFILE_TEMPLATES)}")
    print("\nContainers per region:")
    for region in sorted(regions.keys()):
        print(f"  Region {region}: {regions[region]} containers")
    
    print("\nBase images used:")
    print("  - fedora:43 (Region A, parts of G)")
    print("  - ubuntu:24.04 (Region B, parts of G)")
    print("  - alpine:3.19 (Region C)")
    print("  - debian:bookworm (Region E)")
    
    print("\nDependency patterns demonstrated:")
    print("  - Linear chains (A, E)")
    print("  - Diamond patterns (B, F)")
    print("  - Cross-platform mixing (D)")
    print("  - Bind mount patterns (G)")
    print("  - Wide fan-out (F from A05)")
    print("  - Deep chains up to 8+ levels (E)")
    print("  - Ultimate convergence (H)")
    print("=" * 60 + "\n")


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main function to set up the complex playground"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    playground = os.path.join(current_dir, "playground_complex")
    
    print(f"\nSetting up complex playground at: {playground}")
    print(f"Total containers to create: {len(DOCKERFILE_TEMPLATES)}")
    
    # Create playground root
    ensure_directory_exists(playground)
    
    # Create each container directory and Dockerfile
    created_count = 0
    for container_id, relative_path in DIRECTORY_STRUCTURE.items():
        full_path = os.path.join(playground, relative_path)
        
        if container_id in DOCKERFILE_TEMPLATES:
            dockerfile_content = DOCKERFILE_TEMPLATES[container_id]
            dockerfile_path = write_dockerfile(dockerfile_content, full_path)
            
            # Create supporting files
            create_requirements_file(full_path)
            create_app_files(full_path, container_id)
            
            created_count += 1
            print(f"  [{created_count:2d}/{len(DOCKERFILE_TEMPLATES)}] Created {container_id}: {relative_path}")
        else:
            print(f"  WARNING: No template found for {container_id}")
    
    # Print statistics
    print_statistics()
    
    print(f"Complex playground created at: {playground}")
    print("\nSee COMPLEX_PLAYGROUND_DESIGN.md for full documentation.")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Setup complex playground with 50 Docker containers demonstrating various dependency patterns."
    )
    parser.add_argument(
        "--clean", 
        action="store_true", 
        default=False, 
        help="Clean the complex playground directory before setup."
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        default=False,
        help="Only print statistics, don't create files."
    )
    
    args = parser.parse_args()
    
    if args.stats_only:
        print_statistics()
        exit(0)
    
    if args.clean:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        playground = os.path.join(current_dir, "playground_complex")
        if os.path.exists(playground):
            shutil.rmtree(playground)
            print(f"Cleaned up the complex playground directory: {playground}")
        exit(0)
    
    print("=" * 60)
    print("COMPLEX PLAYGROUND SETUP")
    print("50 Docker Containers with Complex Dependencies")
    print("=" * 60)
    
    main()
    
    print("\nSetup complete!")
    print("Run with --clean to remove the playground.")
    print("Run with --stats-only to see statistics without creating files.")
