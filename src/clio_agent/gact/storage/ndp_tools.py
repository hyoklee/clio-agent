"""Agent discovery through the same NDP catalog owner as the source picker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.storage.service import StorageService


def _service() -> StorageService:
    app, sid = context.active_app(), context.active_session_id()
    session = app.state.sessions.get(sid) if app is not None and sid else None
    if app is None or session is None or app.state.workspaces.get(session.workspace_id) is None:
        raise ValueError("NDP discovery requires an active workspace conversation")
    return app.state.connected_storage


def connected_data_search_ndp(
    query: str = "", organization: str = "", endpoint_id: str = "", offset: int = 0
) -> dict[str, Any]:
    """Find NDP datasets and resources without downloading or connecting them.

    Use connected_data_ndp_organizations to discover organization IDs such as
    earthscope_consortium. organization filters that catalog publisher; it does
    not join an organization or grant its protected Endpoint access. query
    matches catalog metadata with AND between words. Use a few distinctive words,
    not a whole question or synonym list; retry zero matches with fewer words
    before concluding a collection is absent. Returns 50 rows per page, resource IDs and paths,
    never credentials or download URLs. To attach selected resources, call
    connected_data_connect(provider="ndp", root=dataset.id, label=dataset.title,
    configuration={"endpoint_id": dataset.endpoint_id, "resource_ids": [ids]}).
    """
    if offset < 0 or len(query) > 1000 or len(organization) > 512:
        raise ValueError("Use a nonnegative offset and a bounded catalog query")
    service = _service()
    return service.ndp.search(
        query, endpoint_id, organization=organization, offset=offset, limit=50
    )


def connected_data_ndp_organizations(query: str = "", endpoint_id: str = "") -> dict[str, Any]:
    """Find NDP catalog publisher IDs, for example EarthScope, without account setup.

    Pass a returned id and endpoint_id to connected_data_search_ndp. This is
    discovery only: catalog organizations and protected Endpoint role groups
    are different. Account sign-in is obtained through connected_data_status's
    private NDP login_action when a selected resource requires it.
    endpoint_id is a catalog ID returned by this discovery surface, not a saved
    workspace ndpep_ connection ID. For that connection's local organizations,
    discover/invoke its organization operation with the Endpoint tools.
    """
    if len(query) > 1000:
        raise ValueError("Use a catalog organization query of at most 1000 characters")
    return _service().ndp.organizations(query, endpoint_id)


def build_ndp_discovery_tools() -> list[Any]:
    """Expose credential-free discovery to the root source-connection workflow."""
    return [
        native_tool(
            connected_data_search_ndp,
            name="connected_data_search_ndp",
            desc=connected_data_search_ndp.__doc__,
            args={
                "query": {"type": "string"},
                "organization": {"type": "string"},
                "endpoint_id": {"type": "string"},
                "offset": {"type": "integer"},
            },
            title="Search NDP",
            domain="resources",
            read_only=True,
            presentation=ndp_presentation,
        ),
        native_tool(
            connected_data_ndp_organizations,
            name="connected_data_ndp_organizations",
            desc=connected_data_ndp_organizations.__doc__,
            args={"query": {"type": "string"}, "endpoint_id": {"type": "string"}},
            title="NDP organizations",
            domain="resources",
            read_only=True,
            presentation=ndp_presentation,
        ),
    ]


def ndp_presentation(args: Mapping[str, Any], result: Any, structured: Any) -> dict[str, Any]:
    """Show catalog result counts without placing private source locators in Activity."""
    row = structured if isinstance(structured, Mapping) else result
    if not isinstance(row, Mapping):
        return {"summary": "NDP discovery unavailable", "blocks": []}
    key = "datasets" if "datasets" in row else "organizations"
    return {"summary": f"{len(row.get(key, []))} NDP {key}", "blocks": []}
