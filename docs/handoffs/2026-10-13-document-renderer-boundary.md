# OPAL document-rendering failure

The retained OPAL 1 conversation (`sess_6fe306b2a851`) contains two failed
`prepare_document(action="render")` calls: 107.85 seconds and 19.68 seconds,
both returning `msiexec.exe exited 1603`. It contains no `view_image` calls.
The eight-slide PPTX was structurally inspected and published, but its visual
review did not complete. The later checklist replaced the requested rendering
and review with a completed attempt; that does not fulfill the original task.

Read-only session evidence is retained under
`D:/CLIO-Develop/document-renderer-20261013/` as `opal1-messages.json` and
`session-audit.json`. No session message, todo, scientific source or deck was
changed during this investigation. The recorded deck SHA-256 is
`69bc1b8f4aa735938584960a81c99afda0f2eaaec7ea0589966ef1dc8ac26ba2`.

## Access failure

LibreOffice already exists in the managed cache. Its version root has a
protected Windows DACL granting only OWNER RIGHTS, SYSTEM and Administrators.
The parent has inherited sandbox and ordinary user access, but protection at
the version root stops those grants. Thus host-side discovery can report a
renderer that a confined worker cannot discover or execute. The worker then
enters `ensure_office` and attempts MSI extraction inside its sandbox.
Code 1603 is generic; this audit does not claim an MSI-internal diagnosis beyond
the recorded exit. The incorrect provisioning boundary is independently clear.

The two failed run directories also deny host access. `tempfile.mkdtemp` creates
private directories; Python 3.13+ applies a protected owner/administrator ACL
for mode 0700 on Windows. Creating published outputs under the sandbox identity
with that mode excludes the host reader. See
[Python's directory permissions](https://docs.python.org/3.14/library/os.html#os.mkdir).

## Correction

- Prepare Office in the trusted host before confined rendering/recalculation,
  passing its executable explicitly. The confined worker cannot start Office
  installation when the renderer is unavailable. PDF rendering and document
  inspection do not require Office setup.
- Restore parent inheritance on protected managed Office cache/staging roots.
  Inspect one root; repair only when protected. Preserve existing explicit ACEs,
  avoid `/T` and repeated recursive grant passes, and keep the write fence active.
- Create run directories with the output parent's existing Windows ACL from the
  start. POSIX retains mode 0700. Profiles created inside a worker stay private;
  host-created preview staging and Office profiles inherit their parent's grants
  before the confined executor uses them. These repairs touch each new root only.
- Route artifact PDF previews through the same host-side Office preparation,
  including access repair when the managed executable was already discovered.
- Before conversion, reuse successful `prepare_document` render output whose
  source SHA-256 matches this immutable revision and whose PDF still matches its
  recorded hash. Copy and retain it through the existing artifact/lineage path.
  Failed, malformed, changed or escaping outputs are ignored. Later opens use
  the retained rendition directly; a sibling PDF filename alone is insufficient.
- Include `visual_review: "not performed"` in initial/failure manifests. Rendering
  alone still does not assert review.
- Preserve the requested outcome in shared todo guidance and the presentation
  skill. A failed attempt remains blocked; only the user can waive required review.

Added/updated hosted regression coverage for host-first preparation, PDF and
inspection independence, refusal of confined installation, one-time inheritance
repair, preserved contents and output-directory inheritance. Local work is
source inspection and Ruff lint/formatting only: no test suites, native rendering,
model inference, app rebuilds/reloads or OPAL analysis were run. Hosted CI and an
eventual authorized installed-runtime acceptance remain separate from this fix.
