# Long presentation builder commands

The retained OPAL 1 export records a failed 11,671-character shell command. It
embedded a Python presentation builder in a PowerShell here-string, then piped
that whole string into `Set-Content` before running the saved script. It exited
with code 1 and `The command line is too long.` The builder was therefore still
part of the launch command even though it intended to save a `.py` file.

This is below CLIO's configured default 16,000-character input cap. That cap
does not guarantee native launchability: cmd.exe and batch launchers have an
8,191-character bound, and CreateProcessW limits the quoted launch string to
32,767 UTF-16 characters including its terminating NUL. The export does not
record the fully composed native argv, so this audit does not assert which
launcher introduced the tighter bound. See Microsoft's
[cmd.exe limits](https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/command-line-string-limitation)
and [CreateProcessW contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw).

The shared chat prompt and presentation procedure now require substantial
builders to be saved before execution. Use an available tool that really writes
files, or create/append the source in small UTF-8 shell calls, then run the saved
file with the prepared runtime arguments. One giant here-string, heredoc,
encoded command or `-c` argument does not avoid a launcher limit. A proposed
file diff must actually be applied before executing it. Keep builders as
inspectable intermediate files; publish their source only when requested.

Shell failures use one shared recovery instruction for the CLIO input bound,
native launch preflight, spawn-size errors, and completed native shell errors.
Windows preflight counts wrapper arguments, quoting and UTF-16 units and
distinguishes batch launchers from direct executable launches. The shared output
composer recognizes the exact failed-launch diagnostic while retaining stdout,
stderr, exit status and output spill records under the existing result budget.
This applies to foreground and background shell results through their common
composer; successful output quoting the same words is not changed into failure.

Added unit cases for batch/direct bounds, quoting, non-BMP text, native exception
codes and bounded result recovery, plus an MCP regression that preserves the
actual child diagnostic. Local validation is source/diff inspection and Ruff
lint/format only. Tests were authored for hosted CI and were not run locally.
No app build, reload, presentation generation, OPAL analysis, Core change or
existing session mutation was performed. The installed build is unchanged.

This branch and renderer PR #1743 both update the built-in presentation skill:
this branch updates the opening builder instructions; #1743 updates later
render/review guidance. Preserve both through the inspected merge tree.
