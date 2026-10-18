"""Trusted UI control plane for existing NDP Endpoint/service operations."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI

from clio_agent.gact.routes.storage_ndp import Action
from clio_agent.gact.storage.ndp_endpoint_models import (
    EndpointConnectionInput,
    EndpointConnectionUpdate,
    EndpointRequest,
)
from clio_agent.gact.storage.ndp_endpoints import materialize_capture
from clio_agent.gact.storage.service import StorageService


def register_ndp_endpoint_routes(app: FastAPI, service: StorageService, run: Action) -> None:
    """Use the same workspace owner, private NDP account and resource store as other sources."""
    owner = service.ndp_endpoints

    def workspace(wid: str) -> None:
        if app.state.workspaces.get(wid) is None:
            raise KeyError("Workspace not found")

    def account_token() -> str | None:
        account = service.auth.account_login(service.principal, service.store.clio_id, "ndp")
        return service.auth.token(account) if service.auth.connected(account) else None

    @app.get("/v1/workspaces/{wid}/ndp-endpoints")
    async def connections(wid: str, include_hidden: bool = False) -> dict[str, Any]:
        workspace(wid)
        return await run(
            lambda: {
                "endpoints": [
                    owner.describe(row)
                    for row in owner.connections(wid, include_hidden=include_hidden)
                ]
            }
        )

    @app.patch("/v1/workspaces/{wid}/ndp-endpoints/{identifier}")
    async def edit(wid: str, identifier: str, body: EndpointConnectionUpdate) -> dict[str, Any]:
        workspace(wid)

        def change() -> dict[str, Any]:
            record = owner.get(wid, identifier)
            destination_changed = any(
                value is not None and value != getattr(record, name)
                for name, value in body.model_dump().items()
                if name in {"url", "ssh_profile", "authentication"}
            )
            authentication = body.authentication or record.authentication
            token = account_token() if destination_changed and authentication == "ndp" else None
            try:
                return owner.describe(owner.update(wid, identifier, body, token))
            except httpx.HTTPError as exc:
                raise ValueError("Could not discover the Endpoint API: " + str(exc)) from exc

        return await run(change)

    @app.post("/v1/workspaces/{wid}/ndp-endpoints", status_code=201)
    async def connect(wid: str, body: EndpointConnectionInput) -> dict[str, Any]:
        workspace(wid)

        def observe() -> dict[str, Any]:
            try:
                return owner.describe(
                    owner.connect(
                        wid, body, account_token() if body.authentication == "ndp" else None
                    )
                )
            except httpx.HTTPError as exc:
                raise ValueError("Could not discover the Endpoint API: " + str(exc)) from exc

        return await run(observe)

    @app.delete("/v1/workspaces/{wid}/ndp-endpoints/{identifier}")
    async def disconnect(wid: str, identifier: str) -> dict[str, bool]:
        workspace(wid)
        await run(lambda: owner.disconnect(wid, identifier))
        return {"disconnected": True}

    @app.get("/v1/workspaces/{wid}/ndp-endpoints/{identifier}/captures")
    async def captures(wid: str, identifier: str) -> dict[str, Any]:
        workspace(wid)
        return await run(
            lambda: {"captures": [row.model_dump() for row in owner.captures(wid, identifier)]}
        )

    @app.post("/v1/workspaces/{wid}/ndp-endpoints/{identifier}/request")
    async def invoke(wid: str, identifier: str, body: EndpointRequest) -> dict[str, Any]:
        workspace(wid)

        def perform() -> dict[str, Any]:
            record = owner.get(wid, identifier)
            token = None
            if record.authentication == "ndp":
                token = account_token()
            try:
                return materialize_capture(
                    app, owner.invoke(wid, identifier, body, app.state.resource_store, token)
                )
            except httpx.HTTPError as exc:
                raise ValueError("Endpoint request failed: " + str(exc)) from exc

        return await run(perform)

    @app.post("/v1/workspaces/{wid}/ndp-endpoints/{identifier}/browse")
    async def browse(wid: str, identifier: str, body: EndpointRequest) -> Any:
        """Refresh semantic metadata lists independently of saved measurement captures."""
        workspace(wid)

        def read() -> Any:
            record = owner.get(wid, identifier)
            try:
                return owner.browse(
                    wid,
                    identifier,
                    body,
                    account_token() if record.authentication == "ndp" else None,
                )
            except (httpx.HTTPError, TimeoutError) as exc:
                raise ValueError("Could not browse the Endpoint: " + str(exc)) from exc

        return await run(read)
