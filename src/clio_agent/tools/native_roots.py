"""Independent native FastMCP/Docket resources, without a CLIO execution queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp_tasks import TasksExtension

from clio_agent import conf

NativeRootKind = Literal["shell", "storage"]


@dataclass(frozen=True)
class NativeRootSettings:
    """Native backend configuration resolved through CLIO's existing settings."""

    url: str
    queue: str
    concurrency: int = 10


@dataclass(frozen=True)
class NativeRoot:
    """Server resources the application lifespan owns; this holds no task state."""

    server: FastMCP
    extension: TasksExtension
    settings: NativeRootSettings


def resolve_native_root(kind: NativeRootKind) -> NativeRootSettings:
    """Keep native URL/queue/capacity settings and distinct default queue identities."""
    if kind not in {"shell", "storage"}:
        raise ValueError("Unknown native root")
    prefix, environment = f"gact.tasks.{kind}", f"CLIO_TASKS_{kind.upper()}"
    url = conf.resolve(prefix + ".url", env=environment + "_URL", default="memory://", cast=str)
    queue = conf.resolve(prefix + ".queue", env=environment + "_QUEUE", default="", cast=str)
    concurrency = conf.resolve(
        prefix + ".concurrency", env=environment + "_CONCURRENCY", default=10, cast=conf.as_int
    )
    if not url or concurrency < 1:
        raise ValueError("Native roots require a backend URL and positive worker concurrency")
    if not queue:
        queue = f"clio-{kind}"
        if url.startswith("memory://"):
            queue += "-" + uuid4().hex
    return NativeRootSettings(url=url, queue=queue, concurrency=concurrency)


def build_native_roots() -> dict[NativeRootKind, NativeRoot]:
    """Build separate native roots; starting their SDK lifespans remains app-owned."""
    shell, storage = resolve_native_root("shell"), resolve_native_root("storage")
    if (shell.url, shell.queue) == (storage.url, storage.queue):
        raise ValueError("Shell and storage must use independent native queue identities")
    roots: dict[NativeRootKind, NativeRoot] = {}
    configured: tuple[tuple[NativeRootKind, NativeRootSettings], ...] = (
        ("shell", shell),
        ("storage", storage),
    )
    for kind, settings in configured:
        server = FastMCP(f"CLIO {kind}", tasks=True, strict_input_validation=True)
        extension = TasksExtension(
            url=settings.url, name=settings.queue, concurrency=settings.concurrency
        )
        server.add_extension(extension)
        roots[kind] = NativeRoot(server=server, extension=extension, settings=settings)
    return roots
