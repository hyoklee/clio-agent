# Agent SSH execution, 19 October 2026

## Cause and resulting behavior

The retained initial Ares trial ran a local `ssh` subprocess and received
`ssh: connect to host ares.cs.iit.edu port 22: Permission denied` before SSH
authentication. The local shell's network fence forces traffic through its
HTTP proxy. OpenSSH does not automatically use HTTP proxy environment
variables. Approving the shell call, including Bypass checks, does not change
that OS network route. Ares itself was reachable through CLIO's shared SSH
connector. The NDP-specific discovery repair did not establish general agent
SSH execution; that missing path was a separate product gap.

`ssh_execute` now provides remote commands through the existing shared
`SshRoute`/connector. Agents declaring `shell_bash` receive it automatically;
remote-only specialists can explicitly declare it without local shell access.
Unrelated specialists do not receive it, and read-only side sessions withhold
it. Named profiles, custom hosts, usernames, ports, identity paths and ordered
jump aliases follow the same contract as connected storage and NDP services.
Host-key verification and the connector's existing key/agent handling remain.

The tool invokes the actual permission gate before opening the connection.
Ask mode identifies the route and exact command. Denial stops before connection;
bypass produces the usual automatic approval. This does not turn off the local
file/network fence or make raw local `ssh` automatically proxy-aware. Remote
commands follow the remote shell and SSH account's OS permissions; the local
workspace write fence does not constrain that host. This is finite command
execution, not an interactive terminal or password/MFA prompt.

Both output streams are drained fairly and large output uses the existing
session-owned shell spill store. Native presentation reuses the standard
terminal blocks, with the remote destination named in its action and nonzero
exits presented as failures. Cancellation/deadline closes the SSH channel and
reports uncertain remote descendant state rather than claiming a process-tree
kill. The exec-request acknowledgement also has a deadline: Paramiko's channel
read timeout alone does not bound that protocol acknowledgement. A short-lived
guard retains the calling session's cancellation context and closes the channel
if the acknowledgement stalls.

## Actual model requests

Evidence root: `D:/CLIO-Develop/ssh-execution-20261019/`.
Visible conversation:
`http://localhost:5219/workspaces/ws_1b4785b7dd5e/sessions/sess_dc9a7c7f0d89`.
The initial workspace was empty with no NDP source. Sol 6.1 was not given tool
names, skill names, shell commands or answer content.

1. `Can you connect to ares over SSH and tell me which machine and operating system you reached?`
   High reasoning, bypass. The model independently chose one `ssh_execute`
   call, running `hostname; uname -srm; cat /etc/os-release`. Actual exit 0;
   `ares.ares.local`, Ubuntu 22.04.5 LTS, Linux 5.15.0-198-generic, x86_64.
2. `What is the current uptime of ares?`
   Model default effort, Ask first. One SSH call requested `uptime -p; uptime`.
   The actual native UI displayed the Ares destination and exact command.
   The operator selected Allow once under the user's authorized test scope.
   Permission `perm_7e64fd01fa9c` resolved at 18:55:54.734 UTC; the remote
   command reported time 13:55:57 and uptime seven days, 24 minutes, exit 0.
   The card's Computer field identifies the originating CLIO host, DESKTOP;
   its summary names the remote Ares destination. No claim is made that the
   local workspace is the remote working directory.
3. `How much free space is on the root filesystem on ares?`
   Model default effort, bypass, after loading the final code. One
   independently chosen `ssh_execute` call ran `df -h /`, exit 0. The actual
   root filesystem response reported 784 GiB available. Automatic approval
   `perm_48c9223e0c64` has status `auto_approved` and reason
   `approval_mode_bypass`. `final-session.json`, `final-permissions.json` and
   `final-receipt.json` retain this evidence. All three model calls succeeded.

`conversation.json` retains initial conditions. `bypass-session.json` and
`ask-session.json` retain authoritative histories, with `ask-permissions.json`
and `ask-receipt.json` preserving the actual approval before a later development
restart clears the in-memory permission ledger. Both observed calls completed
without tool failures. The first bypass message's authoritative behavior
metadata records bypass; the focused gate test separately verifies the actual
`approval_mode_bypass` automatic-approval row.

The browser displayed stale activity after the development restart, despite
the successful server-side completion. A normal page reload restored the
saved answer. This was a browser delivery issue, not a failed SSH command;
neither a green tool badge nor a stale spinner substitutes for the stored
command output and approval timestamps. `ask-before-ssh.png` is an actual
native UI capture, not a generated interface.
The final native DOM review verified `Run SSH on ares`, the exact `df -h /`
command, exit 0 and both standard terminal sections. A separate attempted
cropped screenshot did not visibly include that expanded output despite the
DOM state; it is not qualified as pixel evidence of the result. The approval
capture remains the accepted image evidence, and the authoritative saved SSH
output is separate.

## Validation

Final focused regression checks passed **72 tests, zero failed/skipped**:

```powershell
uv run --no-sync pytest tests/test_gact/test_ssh_execution.py tests/test_gact/test_tool_instrumentation.py tests/test_gact/test_native_tool_optional_schema.py tests/test_gact/test_github_shell_guidance.py tests/test_gact/test_tool_catalog_schemas.py -q
```

`ssh-final-tests.log` retains the result and existing warnings. The tests
exercise real encrypted SSH channels over loopback,
both output streams, exit status, oversize spill integrity, cancellation,
read and acknowledgement deadlines, real permission-gate allow/deny/bypass,
capability attachment, declaration schemas, side-session restrictions, tool
instrumentation and catalog compatibility. The test SSH peer pins a generated
host key and authenticates a test account; it is distinct from live Ares.

Ruff and Pyright pass. Existing deprecated home-path warnings and native Core
nanobind shutdown leak diagnostics remain outside this change. No homepage,
Core process, host-key policy or published collaborator HTML was changed.

## Contract and presentation follow-up

The user's screenshot exposed a real omission in the **first** call,
`call_ffd3a73fafc9` (2,206 ms). Its persisted result contained stdout, but
`presentation.blocks` was empty. The recorded stdout includes `ares.ares.local`,
the kernel and Ubuntu release information. Later calls already had terminal
blocks. Successful SSH transport did not establish correct presentation of
that initial result, and the original qualification did not catch this.

The implementation now uses the existing CLIO contracts throughout:

| Surface | Declared behavior |
| --- | --- |
| Inputs | Remote-shell command; exactly one named profile or shared `SshRoute`; command deadline after connection; per-stream inline limit. Argument descriptions, defaults and bounds appear in the standard catalog. |
| Outputs | Typed dictionary with `ssh_route`, optional command echo, nullable `exit_code`, `status`, `stop_reason`, `timeout_s`, stdout/stderr and truncation flags. Optional spill receipts describe retained files or save failures. Remote descendant uncertainty is explicit after timeout/cancellation. |
| Errors | Invalid arguments, refused approval and connection failures raise ordinary tool errors. Nonzero command exits are failed results; absent exit status is null rather than a claimed exit code. |
| Running display | The declared start presenter shows the remote destination and exact command through the existing terminal block. This does not claim incremental output streaming. |
| Completed display | The existing terminal presenter displays command, captured output, exit status and saved-output references. Empty capture and uncertain remote process state are explicit. |
| Recorded history | A narrowly scoped compatibility projection recovers missing blocks from the original SSH result dictionary. It changes display only, never reruns the command or edits the ledger. History, session-scoped paging and HTML archive projection use the same retained result. |

`SshCommandResult` supplies the normal catalog's output schema through its return
annotation; `declare_structured_content` carries that same actual result through
the normal observer. There is no SSH-specific UI renderer or new block type.

The architectural reason for the extra tool is a managed remote transport:
it shares profiles, custom hosts, hop chains, authentication and host-key
verification with CLIO's existing connector, and it can be granted independently
of local shell capability. It executes the user's remote shell command, with
no NDP-specific command language. It is **not** an interactive OpenSSH session:
no PTY, password/MFA conversation, persistent shell, file transfer or forwarding
interface is claimed. The remote account's authority is distinct from the local
workspace fence. This trusted application connector is also distinct from the
child-process HTTP proxy; it is not evidence that a raw OpenSSH child traversed
that proxy or acquired its child-egress provenance.

Ordinary `ssh` in Bash should also have a supported route. OpenSSH needs explicit
proxy integration on the enforced fence tier; approving or bypassing a command
does not supply that integration. That remains a separate gap, not a reason to
disable the network fence or describe this tool as full shell SSH support.

Follow-up validation: **77 tests passed, zero failures/skips** (24 SSH transport,
contract and observer cases; 53 shared presentation, instrumentation, optional
schema and catalog cases). `ssh-contract-focused.log` and
`ssh-contract-regression.log` preserve the results in the evidence root. Ruff
and focused Pyright checks pass for the SSH modules, transcript projection and
archive projection. Expanding Pyright to `routes/messages.py` reports an
existing error at line 376 (`list(messages.get(sid, []))` can receive `object`);
the same expression is present in HEAD, outside the changed presentation route.
No clean whole-route type check is claimed. Existing deprecated home-path
warnings and native Core shutdown leak diagnostics remain visible in the log.

After restarting only the development backend, the actual retained conversation
was reloaded in the web UI. Expanding the original 2.2-second call now shows
the command, recorded hostname/kernel/release stdout, Show more and exit 0.
`ssh-restored-output.png` is the actual rendered browser capture. This is
qualification of restored historical display and real loopback SSH execution;
no fresh model-to-Ares trial is claimed for this follow-up. Changes are local,
not merged or released.
