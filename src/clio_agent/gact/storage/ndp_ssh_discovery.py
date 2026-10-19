"""Find an existing NDP API on an explicitly approved SSH destination."""

from __future__ import annotations

import http.client
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

import paramiko

from clio_agent.gact.infrastructure.models import SshRoute
from clio_agent.gact.storage.ndp_endpoint_transport import _ChannelSocket
from clio_agent.gact.storage.sftp import connect_route

MAX_PORTS = 32
MAX_CONTRACT_BYTES = 2 * 1024 * 1024


def published_ndp_ports(client: paramiko.SSHClient) -> list[int]:
    """Prefer explicitly named NDP containers over probing unrelated host services."""
    stdin, stdout, stderr = client.exec_command(
        "docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'", timeout=5
    )
    try:
        raw = stdout.read(65537)
        if len(raw) > 65536 or stdout.channel.recv_exit_status() != 0:
            return []
        ports = set()
        for line in raw.decode("utf-8-sig").splitlines():
            if re.search(r"ndp|ep-api", line, re.IGNORECASE):
                ports.update(int(value) for value in re.findall(r":(\d+)->\d+/tcp", line))
        return sorted(ports) if len(ports) <= MAX_PORTS else []
    finally:
        stdin.close()
        stdout.close()
        stderr.close()


def listening_ports(client: paramiko.SSHClient, platform: str) -> list[int]:
    """Read bounded listener metadata with a fixed command, never model-authored shell text."""
    if platform != "windows":
        published = published_ndp_ports(client)
        if published:
            return published
    command = (
        "powershell -NoProfile -NonInteractive -Command "
        '"Get-NetTCPConnection -State Listen | Select-Object -ExpandProperty LocalPort"'
        if platform == "windows"
        else "ss -ltnH"
    )
    stdin, stdout, stderr = client.exec_command(command, timeout=5)
    try:
        text = stdout.read(65537)
        if len(text) > 65536:
            raise ValueError("SSH listener inventory is too large; provide the Endpoint API URL")
        if stdout.channel.recv_exit_status() != 0:
            raise ValueError("Cannot inspect listeners on this host; provide the Endpoint API URL")
        ports: set[int] = set()
        for line in text.decode("utf-8-sig").splitlines():
            fields = line.split()
            address = (
                line.strip() if platform == "windows" else fields[3] if len(fields) >= 4 else ""
            )
            match = (
                re.fullmatch(r"\d+", address)
                if platform == "windows"
                else re.search(r":(\d+)$", address)
            )
            if match:
                port = int(match[0] if platform == "windows" else match[1])
                if 1 <= port <= 65535 and port != 22:
                    ports.add(port)
        if len(ports) > MAX_PORTS:
            raise ValueError("Too many listeners to inspect safely; provide the Endpoint API URL")
        return sorted(ports)
    finally:
        stdin.close()
        stdout.close()
        stderr.close()


def ndp_contract_at(client: paramiko.SSHClient, port: int) -> str | None:
    """Identify a public NDP OpenAPI contract through one bounded verified SSH channel."""
    channel = None
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    response = None
    try:
        transport = client.get_transport()
        if transport is None:
            raise OSError("The SSH connection closed during Endpoint discovery")
        channel = transport.open_channel(
            "direct-tcpip", ("127.0.0.1", port), ("127.0.0.1", 0), timeout=2
        )
        channel.settimeout(2)
        connection.sock = cast(Any, _ChannelSocket(channel))
        connection.request("GET", "/openapi.json", headers={"Connection": "close"})
        response = connection.getresponse()
        if response.status != 200:
            return None
        raw = response.read(MAX_CONTRACT_BYTES + 1)
        if len(raw) > MAX_CONTRACT_BYTES:
            return None
        document = json.loads(raw)
        paths = document.get("paths", {}) if isinstance(document, dict) else {}
        if isinstance(paths, dict) and {"/organization", "/search", "/dataset"} <= paths.keys():
            return f"http://127.0.0.1:{port}"
    except (OSError, http.client.HTTPException, ValueError, paramiko.SSHException):
        return None
    finally:
        if response is not None:
            response.close()
        connection.close()
        if channel is not None:
            channel.close()
    return None


def discover_ndp_ssh_urls(route: SshRoute) -> list[str]:
    """Find existing root-mounted APIs without credentials, installation or remote changes.

    Discovery reads at most 32 loopback listeners and their public OpenAPI
    contracts. It never forwards an NDP token, trusts a redirect, or starts a
    service. Reverse-proxy subpaths and hosts without listener inspection need
    an explicit URL. Multiple matches remain a user choice.
    """
    client = connect_route(route)
    try:
        ports = listening_ports(client, route.platform)
        with ThreadPoolExecutor(max_workers=4) as pool:
            return [
                url for url in pool.map(lambda port: ndp_contract_at(client, port), ports) if url
            ]
    finally:
        client.close()
