# National Data Platform connected source

NDP is available in Settings → Data sources and the workspace Attach picker.
The account is shared across workspaces on the connected CLIO. The picker
loads catalog results, filters names/descriptions/files as the user types, and
searches the remote catalog after a short debounce. Resource selections survive
searches and can be reviewed together. Continue connects only the selected IDs
and opens the same Download/Link review used by the other sources.
Sources appear in Files and use the existing connected-data tools, immutable
resource custody, downloaded copies and content hashing when bytes are read.
Connecting saves catalog metadata. The user explicitly chooses Download or Link;
linking indexes the selected names, while downloading copies their contents.

## Authentication

The shipped defaults are the registered **public** Keycloak client `clio` on
`https://idp-test.nationaldataplatform.org/realms/NDP`. There is no client secret.
CLIO discovers the realm endpoints and uses device authorization with S256
PKCE and `openid offline_access`. It opens the complete verification link,
displays the user code and polls at the realm's interval. `slow_down` adds five
seconds. Cancellation, denial and expiry invalidate the pending flow.

Access/refresh tokens remain in the existing private storage credential vault;
the browser, conversation and tool results receive no tokens. Refresh runs
before expiry under the account owner's lock, preserves/rotates the refresh
token and survives restart. A changed issuer or client requires a new login.
Sign-out attempts refresh-token revocation and forgets local grants even if
the realm cannot be reached. Userinfo supplies a display name only. Token
role claims never determine resource access.

Distributor overrides:

```dotenv
CLIO_STORAGE_NDP_ISSUER=https://idp-test.nationaldataplatform.org/realms/NDP
CLIO_STORAGE_NDP_CLIENT_ID=clio
```

A production realm needs its own registered public device-flow client. The NDP
team renamed the test client from `cilo` to `clio`; the earlier registration
message is obsolete. The supplied working flow uses Keycloak directly rather
than the AAI device wrappers.

## Catalogs and Endpoints

Discovery reuses `NDPClient` from the pinned clio-kit science MCP. Without
overrides it uses that client's existing public global catalog. CLIO loads
the installed client; it does not launch another MCP process or maintain a
second catalog protocol implementation.

Configure the deployment's actual Endpoints on the CLIO service, for example:

```dotenv
CLIO_STORAGE_NDP_ENDPOINTS='[{"id":"lab","name":"Lab Endpoint","url":"https://your-endpoint.example/api","server":"local","authenticated":true}]'
```

The example address is a placeholder. Use the actual ep-api base URL, including
any reverse-proxy prefix. `server` selects the existing NDP client's `local` or
`global` catalog. Endpoint IDs must be unique. `authenticated: true` explicitly
permits sending the user's NDP bearer beneath that HTTPS Endpoint URL. Catalog
metadata and arbitrary resource URLs cannot add credential destinations.

CLIO asks each authenticated Endpoint's `/user/info` for its live
`effective_role`, which is derived through NDP's AAI. Viewer/writer/admin give
a Viewer badge; an explicit denial gives Request access. Missing role data
or an AAI outage produces no inferred badge. Browsing remains available.
Only my groups includes Endpoints whose live access check succeeds and reports
when the check cannot be made. These are Endpoint access indications, not a
promise that every resource is readable.

The reported test-AAI role-query failure does not require another client
implementation. Its authenticated reads remain subject to the service's actual
authorization response.

The account-level role/group inspection endpoint on the test AAI is
`POST https://idp-test.nationaldataplatform.org/api/information`, with the user's
access token in the Authorization header. This differs from an Endpoint's
`/user/info`, which evaluates access to that Endpoint. CLIO's public client does
not have a client secret or send `X-Client-Assertion`. Account memberships alone
do not establish that a particular resource is readable.

## Reading and custody

The provider dispatches only selected catalog resources:

| Resource | Read route |
| --- | --- |
| HTTP(S) | Stream its URL. Bearer only beneath an explicitly configured HTTPS Endpoint. |
| `pelican://osg-htc.org/...` or `osdf://...` | Endpoint `GET /pelican/download?path=...&federation=osdf&stream=true` |
| `pelican://path-cc.io/...` | Same read route with `federation=path-cc` |
| `s3://bucket/key` | Endpoint `GET /s3/objects/bucket/key` |

Authenticated redirects to another origin receive **no bearer**. Readers own
and close their response/client, use bounded buffers and enforce a 512 MiB
limit. HTTP status errors are sanitized. A denied S3 read explains that current
ep-api policy requires writer access even to download. CLIO still exposes no
NDP write, upload, metadata mutation or deletion operation. Local editable
downloads follow existing copy semantics and never publish back to NDP.

Selected IDs/URLs are saved privately with the source. Files → refresh updates
catalog revisions and signed URLs while retaining the approved resource set
and names. Changed Endpoint configuration requires reconnection. Unknown
Pelican federation mappings and unsupported transports fail explicitly instead
of silently choosing another federation or credential route.

## Qualification

Automated protocol fixtures cover discovery, PKCE, pending/slow-down/terminal
errors, cancellation, restart, concurrent refresh, rotation, revocation and
realm/client ownership. The source integration uses the real clio-kit client
against a local HTTP server, attaches metadata, restarts the storage owner and
reads actual bytes through linked-file custody. Transport tests cover Pelican,
S3, read-only enforcement, access-check outages and redirect credential scope.
Browser fixtures exercise the real repository decoders and picker in both
themes and at a narrow viewport.

These fixtures do not claim a fresh human NDP sign-in or successful protected
reads through an NDP Endpoint. The supplied user script established the device
login path; live Endpoint role assignments and the test AAI remain external
acceptance conditions.

On October 18, 2026, a fresh human sign-in through the actual CLIO UI with the
renamed `clio` client succeeded. The backend saved the offline grant and
successfully refreshed and rotated it after the test forced the local expiry
timestamp. The AAI `/api/information` returned HTTP 200 and no group memberships
for the test account. The saved login survived restarting the backend. Signing
out through the UI removed it, and NDP rejected the revoked refresh token with
`invalid_grant`. The existing public catalog returned HTTP 400 because its
Solr service could not connect; protected reads still need a working Endpoint
that accepts the test realm and the account's intended access grant. A forced
local expiry exercises refresh but does not claim an elapsed five-hour token
lifetime.

API contracts checked against
[ep-api read authorization](https://github.com/national-data-platform/ep-api/blob/main/docs/roles-and-permissions.md),
[Pelican routes](https://github.com/national-data-platform/ep-api/blob/main/api/routes/pelican_routes.py)
and [S3 object routes](https://github.com/national-data-platform/ep-api/blob/main/api/routes/minio_routes/object_routes.py).
