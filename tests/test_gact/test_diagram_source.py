"""Folder links stay navigation rather than scripts or access grants."""

from __future__ import annotations

import pytest

from clio_agent.gact.a2ui_catalogs.diagram_source import validate_diagram_source


@pytest.mark.parametrize(
    "path",
    [
        "reports",
        "raw%20data",
        "analysis/run-1",
        ".",
        "@permitted/source",
        "reports%23draft",
        "survey%3F",
    ],
)
def test_relative_folder_link_is_declarative(path: str) -> None:
    validate_diagram_source(
        f'flowchart LR\n stage[Review] --> done[Done]\n click stage "workspace-folder:{path}" "Open folder"'
    )


@pytest.mark.parametrize(
    "target",
    [
        "/etc",
        "C:/Users",
        "..",
        "reports/../private",
        "%2e%2e/secrets",
        "%2fetc",
        "%5c%5cserver/share",
        "%00",
        "%GG",
        "%ff",
        "https://example.org",
        "reports?x=1",
    ],
)
def test_folder_navigation_does_not_widen_the_workspace(target: str) -> None:
    with pytest.raises(ValueError):
        validate_diagram_source(f'flowchart LR\n A --> B\n click A "workspace-folder:{target}"')


@pytest.mark.parametrize(
    "directive",
    [
        "click A callback",
        'click A "https://example.org"',
        "click A javascript:alert(1)",
        "A-->B; click A callback",
        "%%{init: {}}%%",
        "<script>run()</script>",
    ],
)
def test_executable_diagrams_stay_rejected(directive: str) -> None:
    with pytest.raises(ValueError):
        validate_diagram_source(f"flowchart LR\n {directive}")


def test_repeated_folder_targets_are_ambiguous() -> None:
    with pytest.raises(ValueError, match="repeats"):
        validate_diagram_source(
            'flowchart LR\n A-->B\n click A "workspace-folder:one"\n click A "workspace-folder:two"'
        )


def test_click_is_allowed_as_an_ordinary_label() -> None:
    validate_diagram_source("flowchart LR\n A[Click to inspect] --> B[Continue]")


def test_left_facing_arrows_are_not_html() -> None:
    validate_diagram_source("flowchart LR\n A <--> B")
