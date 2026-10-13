"""Backend identities use actual SDK transports, including their native session scope."""

from clio_agent.tools.mcp_runtime import make_mcp_client


def test_task_extension_holds_the_sdk_transport_and_distinct_backend_identity() -> None:
    """URL construction must retain the actual transport and backend session lookup."""
    from clio_agent.tools.mcp_task_extension import ClioTasksClientExtension, backend_identity

    clients = [make_mcp_client(f"http://127.0.0.1:{port}/mcp") for port in (19001, 19002)]
    identities = []
    for client in clients:
        extension = next(
            item for item in client._extensions_arg if isinstance(item, ClioTasksClientExtension)
        )
        assert extension._clio_transport is client.transport
        assert extension.backend == backend_identity(client.transport)
        assert extension.backend.locator["transport"] == "http"
        identities.append(extension.backend.server_id)
    assert identities[0] != identities[1]


def test_independent_inprocess_servers_with_the_same_name_cannot_collide() -> None:
    from fastmcp import FastMCP

    from clio_agent.tools.mcp_task_extension import backend_identity

    first, second = FastMCP("same-name"), FastMCP("same-name")
    original = make_mcp_client(first)
    repeated = make_mcp_client(first)
    independent = make_mcp_client(second)
    assert backend_identity(original.transport) == backend_identity(repeated.transport)
    assert backend_identity(original.transport) != backend_identity(independent.transport)
