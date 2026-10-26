# Managed infrastructure

CLIO can install, start, stop, verify and uninstall the services an agent needs:
model servers, a model router, provenance capture, web search and remote CLIO itself.
It does this on the machine running CLIO or on an SSH or HPC host. This page says what
CLIO offers on each kind of host and what the host must already provide.

## How CLIO installs a service

Each service has one or more **variants**. Every variant uses one of two methods.

- **Native.** CLIO creates a private environment with `uv`. It downloads upstream
  **prebuilt** binaries and wheels, each pinned by version and SHA-256. No container
  runtime and no root access are needed.
- **Container.** CLIO runs upstream images pinned by digest with Docker or Podman, or
  with Apptainer on Linux clusters. Flowcept and CMF also have a mixed variant: the
  application runs natively and only its databases run in containers.

**CLIO never compiles anything on the host.** It does not build from source and does
not need a C or C++ compiler, `make` or `cmake`. Before a native install finishes,
CLIO runs each fetched binary once. If the binary cannot run on this host, because
glibc is too old or a system library is missing, the install is refused. The message
names the missing piece, and the container variant becomes the supported path on that
host. A test (`test_no_native_installer_compiles_on_the_host`) keeps compile steps out
of the native installers.

## What each host can run

The tables below are generated from CLIO's service catalog, the same code that decides
what the Infrastructure page offers. A variant appears only where the catalog marks it
compatible. "Without a container runtime" is what a host with only `uv` gets. The last
column shows what Docker, Podman or Apptainer adds. Apptainer is Linux only and offers
the same container variants as Docker there. Linux hosts are listed as SSH or HPC
targets. Windows and macOS are listed as the machine running CLIO, which is where their
native services install. Versions are in parentheses.

These tables state what CLIO offers, not that each variant has run on every
distribution. For verified host requirements, see the next section.

<!-- BEGIN GENERATED: support matrix (scripts/render_infrastructure_support.py) -->

### Linux x86-64 with an NVIDIA GPU

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Native CUDA (0.28.0); Native CUDA + attention (0.27.0) | NVIDIA CUDA (0.28.0); CPU (0.28.0) |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | NVIDIA CUDA (native) (b11206); CPU (native) (b11206); Vulkan (AMD, Intel or NVIDIA) (native) (b11206) | NVIDIA CUDA (b11206); Vulkan (b11206); CPU (b11206) |
| Ollama | NVIDIA CUDA (native) (0.34.4); CPU (native) (0.34.4); Vulkan (AMD, Intel or NVIDIA) (native) (0.34.4) | CPU (0.34.4); NVIDIA CUDA (0.34.4) |
| Flowcept | Native application + native/site databases (e638b4e2) | Native application + container databases (1.0.3) |
| HPE CMF | Native application + native/site databases (53d9c3e5) | Native application + container databases (53d9c3e5) |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Published release (0.9.5b8) | Nothing more |

### Linux x86-64 with an AMD GPU

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | AMD ROCm (0.28.0); CPU (0.28.0) |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | CPU (native) (b11206); Vulkan (AMD, Intel or NVIDIA) (native) (b11206) | Vulkan (b11206); CPU (b11206) |
| Ollama | AMD ROCm (native) (0.34.4); CPU (native) (0.34.4); Vulkan (AMD, Intel or NVIDIA) (native) (0.34.4) | CPU (0.34.4); AMD ROCm (0.34.4) |
| Flowcept | Native application + native/site databases (e638b4e2) | Native application + container databases (1.0.3) |
| HPE CMF | Native application + native/site databases (53d9c3e5) | Native application + container databases (53d9c3e5) |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Published release (0.9.5b8) | Nothing more |

### Linux x86-64 with an Intel GPU

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Native Intel XPU (host); Native Intel XPU + attention (host) | CPU (0.28.0) |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | Vulkan (AMD, Intel or NVIDIA) (native) (b11206); CPU (native) (b11206) | CPU (b11206) |
| Ollama | Vulkan (AMD, Intel or NVIDIA) (native) (0.34.4); CPU (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Native application + native/site databases (e638b4e2) | Native application + container databases (1.0.3) |
| HPE CMF | Native application + native/site databases (53d9c3e5) | Native application + container databases (53d9c3e5) |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Published release (0.9.5b8) | Nothing more |

### Linux x86-64, CPU only

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | CPU (0.28.0) |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | CPU (native) (b11206) | CPU (b11206) |
| Ollama | CPU (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Native application + native/site databases (e638b4e2) | Native application + container databases (1.0.3) |
| HPE CMF | Native application + native/site databases (53d9c3e5) | Native application + container databases (53d9c3e5) |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Published release (0.9.5b8) | Nothing more |

### Linux arm64 with an NVIDIA GPU

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Native CUDA (0.28.0); Native CUDA + attention (0.27.0) | NVIDIA CUDA (0.28.0) |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | CPU (native) (b11206); Vulkan (AMD, Intel or NVIDIA) (native) (b11206) | NVIDIA CUDA (b11206); Vulkan (b11206); CPU (b11206) |
| Ollama | NVIDIA CUDA (native) (0.34.4); CPU (native) (0.34.4); Vulkan (AMD, Intel or NVIDIA) (native) (0.34.4) | CPU (0.34.4); NVIDIA CUDA (0.34.4) |
| Flowcept | Not available | Native application + container databases (1.0.3) |
| HPE CMF | Not available | Native application + container databases (53d9c3e5) |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Published release (0.9.5b8) | Nothing more |

### Linux arm64, CPU only

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | Nothing more |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | CPU (native) (b11206) | CPU (b11206) |
| Ollama | CPU (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Native application + container databases (1.0.3) |
| HPE CMF | Not available | Native application + container databases (53d9c3e5) |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Published release (0.9.5b8) | Nothing more |

### Windows x86-64 with an NVIDIA GPU

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | CPU (0.28.0) |
| Model router | Not available | Nothing more |
| llama.cpp | NVIDIA CUDA (native) (b11206); CPU (native) (b11206); Vulkan (AMD, Intel or NVIDIA) (native) (b11206) | CPU (b11206) |
| Ollama | NVIDIA CUDA (native) (0.34.4); CPU (native) (0.34.4); Vulkan (AMD, Intel or NVIDIA) (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Nothing more |
| HPE CMF | Not available | Nothing more |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Not available | Nothing more |

### Windows x86-64 with an AMD GPU

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | CPU (0.28.0) |
| Model router | Not available | Nothing more |
| llama.cpp | Vulkan (AMD, Intel or NVIDIA) (native) (b11206); CPU (native) (b11206); AMD ROCm (native) (b11206) | CPU (b11206) |
| Ollama | Vulkan (AMD, Intel or NVIDIA) (native) (0.34.4); CPU (native) (0.34.4); AMD ROCm (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Nothing more |
| HPE CMF | Not available | Nothing more |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Not available | Nothing more |

### Windows x86-64, CPU only

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | CPU (0.28.0) |
| Model router | Not available | Nothing more |
| llama.cpp | CPU (native) (b11206) | CPU (b11206) |
| Ollama | CPU (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Nothing more |
| HPE CMF | Not available | Nothing more |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Not available | Nothing more |

### Windows arm64

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | Nothing more |
| Model router | Not available | Nothing more |
| llama.cpp | CPU (native) (b11206) | CPU (b11206) |
| Ollama | CPU (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Nothing more |
| HPE CMF | Not available | Nothing more |
| CLIO Web Search | Not available | Container (0.3.2) |
| SearXNG | Not available | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Not available | Nothing more |

### macOS on Apple silicon

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | Nothing more |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | Apple Metal (native) (b11206) | CPU (b11206) |
| Ollama | Apple Metal (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Nothing more |
| HPE CMF | Not available | Nothing more |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Not available | Nothing more |

### macOS on Intel

| Service | Without a container runtime | Added by Docker, Podman or Apptainer |
| --- | --- | --- |
| vLLM | Not available | CPU (0.28.0) |
| Model router | LiteLLM Proxy (native) (1.102.1) | Nothing more |
| llama.cpp | CPU (native) (b11206) | CPU (b11206) |
| Ollama | CPU (native) (0.34.4) | CPU (0.34.4) |
| Flowcept | Not available | Nothing more |
| HPE CMF | Not available | Nothing more |
| CLIO Web Search | Native gateway + SearXNG (0.3.2) | Container (0.3.2) |
| SearXNG | Native (uv) (2026.8.11+e8e710e42) | Nothing more |
| CLIO Relay | Released uv tool (1.6.8) | Nothing more |
| CLIO | Not available | Nothing more |

<!-- END GENERATED: support matrix -->

## Native host requirements (Linux)

Native services use upstream Linux binaries. Upstream builds them for current
distributions, so the host's C library and system libraries decide whether they run.

| Component | Upstream build | Needs on the host |
| --- | --- | --- |
| Valkey 8.1.3 (Flowcept's message queue) | Valkey's Ubuntu 22.04 build | glibc 2.34 or newer, `libssl.so.3`, `libsystemd.so.0` |
| PostgreSQL 17.6 (CMF's database) | theseus-rs/postgresql-binaries | glibc 2.34 or newer, `libssl.so.3`, libxml2, Kerberos (`libgssapi_krb5`), lz4, zstd |
| MongoDB 8.0.14 (Flowcept's store) | MongoDB's per-distribution builds | One of Ubuntu 20.04, 22.04 or 24.04, Debian 12, RHEL/Rocky/Alma 8, or SLES/openSUSE Leap 15. SUSE 15 also needs `libopenssl1_1`. |
| llama.cpp b11206 | llama.cpp's Ubuntu builds: CPU (x86-64, arm64), Vulkan (x86-64, arm64), CUDA 12.8 (x86-64) | glibc 2.34 or newer, libstdc++ from GCC 12 or newer (`GLIBCXX_3.4.30`), `libgomp.so.1`. CUDA also needs an NVIDIA driver; CLIO supplies the CUDA 12.8 runtime and cuBLAS from NVIDIA's wheels. |

llama.cpp publishes no Linux ROCm build. On AMD GPUs use the native Vulkan build or a
container variant.

### Checked distributions

Checked on 2026-10-26 by running each pinned binary's `--version` in the distribution's
official container image, after installing the system libraries listed above:

| Distribution | glibc | Valkey | PostgreSQL | llama.cpp (CPU) |
| --- | --- | --- | --- | --- |
| Ubuntu 24.04 | 2.39 | runs | runs | runs |
| Ubuntu 22.04 | 2.35 | runs | runs | runs |
| openSUSE Leap 15.6 / SLES 15 SP6 | 2.38 | runs | runs | runs |
| Rocky Linux 9 / RHEL 9 | 2.34 | runs | runs | does not run: libstdc++ is GCC 11 |
| openSUSE Leap 15.5 / SLES 15 SP5 | 2.31 | does not run: glibc | does not run: glibc | does not run: glibc |
| Rocky Linux 8 / RHEL 8 | 2.28 | does not run: glibc, no OpenSSL 3 | does not run | does not run |

On a host whose binaries do not run, such as SLES 15 SP5 or RHEL 8 (common on HPC
systems), use the container variants: Flowcept and CMF with container databases, and
the container model servers. On clusters that is usually Apptainer.

The llama.cpp Vulkan and CUDA builds have not been checked on a GPU host yet.

## Updating this page

The support tables are generated from the catalog:

```sh
uv run python scripts/render_infrastructure_support.py          # rewrite the tables
uv run python scripts/render_infrastructure_support.py --check  # fail when out of date
```

`tests/test_scripts/test_render_infrastructure_support.py` runs the check, so a catalog
change that alters support fails CI until this page is regenerated. The requirements
and the checked-distribution table above are maintained by hand. Re-check them whenever
a pinned binary changes.
