# NDP Endpoint SSH routes

The former Endpoint editor accepted only a raw SSH profile string. It could
not express the shared connection route through a login host to a custom
compute destination.

## Implementation

- The Endpoint editor now uses the existing `SshHostPicker`,
  `SshConnectionRoute` and `SshHostDialog`. Its inventory belongs to the
  connected CLIO: saved infrastructure hosts plus explicit OpenSSH aliases,
  including included configuration files. Desktop authentication and folder
  browsing are not prerequisites for an Endpoint HTTP request.
- Custom destinations support username, port, a key path on the connected
  CLIO and an ordered chain of OpenSSH jump references. Jump aliases resolve
  through that CLIO's OpenSSH configuration. No passwords or private-key
  contents enter an Endpoint record.
- Endpoint connections, capture origins and upload receipts reuse the existing
  shared `SshRoute` contract. HTTP discovery, catalog/service requests,
  streaming captures and uploads use the shared SSH connector. Legacy single
  `ssh_profile` records remain valid.
- The saved route is a reviewed snapshot. Route changes trigger API
  rediscovery; an explicit null clears SSH for a direct connection. A rename
  of a legacy Endpoint does not migrate its destination or force rediscovery.
- The shared picker now includes custom saved hosts, retains a saved host's
  jump chain, and preserves nondefault ports in custom jump references.

## Checks and their limits

59 focused backend tests pass across Endpoint operations, workflows, artifact
publication, the SSH route contract/profile inventory and SFTP. 67 distinct
focused UI tests pass across the Endpoint panel/browser, shared route/picker,
Desktop and browser SSH source selectors and host helpers. These are controlled
tests, not evidence of a connection to a real compute node.

The custom-node UI test selects a saved login alias, adds a compute host in the
shared dialog, sets its user/port/key path, saves the host without accidentally
submitting the Endpoint form, and checks that the complete route reaches the
Endpoint request. A second test selects a saved custom host with an existing
jump chain. Backend transfer tests pass the exact route to the shared connector
and exercise real local HTTP discovery and multipart upload/read-back over a
test channel, including closure. Those tests substitute the SSH handshake;
they do not establish real multi-hop authentication.

Backend Pyright and focused Ruff checks pass. The web type check, focused
Oxlint and frontend reuse, size, presentation, brand, ownership and icon guards
pass. The browser regression fixture was updated for the selector but was not
run as live acceptance.

## Actual running preview

The actual Attach dialog at port 5219 was inspected using the user's retained
session. It renders the shared route editor and accepts an unsaved example
`ares → ares-comp-11`. No connection or new Endpoint was submitted.

The backend at port 8209 is still the previous process. Its new shared-profile
inventory route returns HTTP 404; the real UI shows this error. This is not a
successful live SSH acceptance run. The genuine screenshot, with the error
visible, is
`D:/CLIO-Develop/ndp-ssh-target-20261019/real-editor-backend-update-pending.png`.

Automatic approval review rejected starting a temporary Core lease holder with
only `blocked by policy`. The holder was intended to preserve the existing
Core during a backend restart. No holder was started, and neither the backend
nor Core was stopped. Backend activation and real SSH connection acceptance
remain outstanding.

## API sign-in clarification and fresh Ares checks

The former labels **Public access** / **My NDP account** conflated data access
with account-token forwarding. They are now **No NDP sign-in** / **Use my NDP
sign-in**, under **API sign-in**, with an explanation for both choices and a
separate SSH authentication note. Fifteen focused Endpoint panel/browser tests
pass; focused lint passes. The genuine preview screenshot is
`D:/CLIO-Develop/ndp-ssh-target-20261019/api-sign-in-explained.png`.

Fresh operator checks used the existing single-profile `ares` route to the
actual remote API at `http://127.0.0.1:8002`, with no NDP account token:

| Read | Result |
| --- | --- |
| Health and readiness | Both HTTP 200. Local CKAN and Kafka report up; MinIO is disabled. |
| Local organizations | HTTP 200; `services`. |
| Local catalog search | HTTP 200; registered EarthScope FDSN Station Service. |
| Resource listing | HTTP 200; its service resource. |
| Actual proxied II.BFO station query | HTTP 200; 48.3301 N, 8.3296 E, elevation 638 m. |
| User identity without an account token | HTTP 401. |

The same identity operation through CLIO's existing Ares connection, configured
to use the saved NDP account, failed with upstream HTTP 401 and the nested cause
`502: Authentication service is experiencing internal issues`. CLIO exposes
this as a permission failure. This establishes working SSH/public API access,
not working protected-account access. It also does not establish an active
Kafka producer, consumed live measurements, uploads or a compute-node hop.

The initial operator probe accidentally used `search_terms` instead of the
advertised GET parameter `terms`, returning 422. It was corrected after reading
the contract. An attempt to run user identity through the listing-only browse
route was rejected locally; identity was then checked through the proper
operation request route. Both diagnostic mistakes are retained rather than
attributed to NDP. Evidence lives beside the screenshots in
`ares-readonly-initial.json`, `ares-readonly-recheck.json`,
`ares-saved-account-recheck.json` and `ares-saved-account-request-recheck.json`.

These are fresh operator diagnostics through actual services, not a fresh
model/skill benchmark. The earlier recorded Sol II.BFO agent session remains
separate evidence of agent behavior.

## Activation and SSH address discovery for the visible showcase

The preview was restarted normally on 2026-10-19. The shared SSH inventory
route is now active; the earlier activation gap above is historical. The
original rejected temporary lease-holder action was not retried.

A fresh request, `Can you connect to the NDP endpoint on ares (ssh ares)?`,
exposed a missing-address discovery gap. The first trial tried sandboxed shell
SSH, which the network fence blocked. This is retained as
`D:/CLIO-Develop/ndp-showcases-20261019/ares-initial-failed.json` and is not
successful agent acceptance.

The existing Endpoint connection tool now accepts an omitted API URL with an
explicit SSH profile or shared route. After approval it reads bounded listener
metadata and public OpenAPI contracts through the verified shared SSH
connector. Named NDP containers are preferred; fallback inspection is limited
to 32 loopback listeners, with bounded response bytes/time and four concurrent
probes. No account token is sent during discovery. No installation, service
start, remote mutation, relaxed host-key check or change to the shell network
fence is involved. A second approval names the discovered exact destination
before connection/account use. Ambiguous matches require selection.

Sixteen focused discovery/workflow/route tests pass; Ruff and Pyright pass.
Tests substitute the SSH handshake and transfer actual HTTP bytes over local
sockets. A direct production-helper check on actual Ares found only
`http://127.0.0.1:8002`.

The fresh visible Sol 6.1 conversation `sess_a0191620b554` used that tool
independently with an empty URL and `ssh_profile="ares"`, then captured HTTP
200 from the actual health operation. Subsequent actual local catalog and
EarthScope station-proxy requests also returned 200. A protected status
request returned 401 without an NDP account token; this boundary is retained
in the conversation and is not successful protected-operation acceptance.
Further scientific/stream/export qualification is still in progress.
