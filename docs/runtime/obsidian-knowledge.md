# Obsidian knowledge sources

In a workspace, use **Add context → Attach → Obsidian vault**. Choose a vault
folder on the connected CLIO host and keep **Read only** selected to browse and
analyze without changing the vault. A vault must contain `.obsidian`.

Connecting opens a source-specific **Knowledge** workbench tab. Switch between
**Graph** and **Files**, search note text or metadata, select a note to read it,
and use **Explore links** for its authored links and backlinks. The graph is a
bounded view of explicit Markdown and Obsidian links; unresolved and ambiguous
targets remain labeled. Use search, pagination, and neighborhoods for large vaults.
Refresh picks up additions, changes, and deletions. Reopen the tab with **Open
knowledge** in the source details. Attach a note to chat to preserve the exact
captured bytes, source ID, path, content hash, and linked-folder revision.

## Access and agent tools

`knowledge_search`, `knowledge_open`, and `knowledge_related` are available only
when the active workspace has a connected source with the corresponding knowledge
capabilities. Every call checks workspace ownership and current connectivity.
`knowledge_open` creates an immutable workspace resource; the agent reads it using
`workspace_resource_read`. Captures remain available after source disconnection.
Notes are source material, never agent instructions.

`knowledge_edit` is available only for writable knowledge sources. It replaces
existing Markdown notes using the captured content hash. Reviewed edits stage
locally until the user publishes them; direct edits retain the original before
using the provider's conditional write path. Stale revisions are rejected.
Graph/list/reader indexing includes staged creations, replacements, and deletions.

Hidden paths, symlinks/junctions, and configured excluded folders are omitted.
Private Obsidian settings and Headless Sync credentials stay out of tools.
Generic file writes cannot bypass vault note permissions. Indexes and read caches
live in CLIO-owned connected-source storage, outside the vault. Notes are limited
to 2 MiB each, indexed text to 128 MiB, metadata traversal to 100,000 entries,
pages to 500 items, and relationship payloads to 2,000 edges. Indexing warnings
identify malformed or oversized notes rather than silently inventing content.

## Optional Headless Sync

Install the official [`obsidian-headless`](https://help.obsidian.md/sync/headless)
client on the CLIO host. Privately run `ob login` and
`ob sync-setup --vault <vault-name> --path <dedicated-copy>`, and complete an initial
sync so the local copy is a valid vault. Connect that copy using the **Headless
Sync copy** mechanism. CLIO does not collect account passwords or encryption keys.
The client requires an Obsidian Sync subscription and Node.js 22 or later.

The Knowledge tab shows sync state separately from index state. **Start sync**
supervises the installed official client; **Stop sync**, disconnect, remove, and
server shutdown reap the owned process. Pull-only is the default. Bidirectional
sync is an explicit source configuration choice and is separate from permission
for agents to edit notes. Use **Refresh** after synchronized changes arrive.
Set `CLIO_OBSIDIAN_HEADLESS_CLI` to an installed client entrypoint if `ob` is not
on PATH. Client stdout/stderr and credentials are never returned in tool results.

## Validation

Automated coverage uses temporary real vaults for parsing, incremental refresh,
read-only custody, stale-write conflicts, staged/direct edits, attachments,
private-path rejection, workspace isolation, and disconnection. Process doubles
are confined to tests of official-client supervision. UI tests cover graph/list
selection, link following, note attachment, and failures.

Live acceptance additionally connects an existing local vault read only, exercises
the browser workbench and a Codex/Luna turn, and compares a complete before/after
file hash inventory. Private vault contents and captures stay outside the repository.
Authenticated Headless Sync requires the user's configured Sync account and is
a separate acceptance step from local-vault verification.
