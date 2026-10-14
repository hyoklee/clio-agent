# Confined shell timing

The retained 81.65-second no-op could not be fully attributed: legacy Windows
logs accounted for 35.22 seconds of workspace preparation, but the tool reported
only one total duration. The native-runtime selection correction is already
merged. This follow-up makes future command delays distinguishable without
running new probes, sampling threads or inspecting workspace contents.

The built-in shell logs five elapsed wall-time stages under its existing capture
call ID: environment preparation, confinement composition, process start,
child lifetime and output draining. Environment denial and failures retain their
stage; process launch failures, foreground timeout and cancellation have explicit
outcomes. Background acceptance logs the handoff only; task custody and background
execution are unchanged.

Child lifetime includes the sandbox runtime's preparation, the requested command
and its process shutdown. It must not be interpreted as the command's execution
time alone. These are wall times, not CPU attribution. The new records omit
command text and add no fields to the model-facing result or product controls.
They do not retroactively explain the unresolved earlier time or establish that
all CPU-spike causes are fixed.

The existing actual-shell regression now checks that all five stages share one
call ID and omit command contents. Ruff lint/formatting are the only local code
checks for this follow-up. Hosted CI supplies automated qualification; no local
tests, native probes, model inference, application rebuilds or reloads were run.
