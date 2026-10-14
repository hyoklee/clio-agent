# Office artifact transport in session exports

The user's `D:/Libraries/Downloads/OPAL-1.transcript.html` (SHA-256
`f064768257db00a3636ea6ceeaa7a653f4782ddd5e36231b1cef263aa73c7111`)
records a snapshot failure for the published PowerPoint artifact:
`gact_http_response_unreadable: decode text body: invalid utf-8 sequence`.
This is separate from the rendering failure tracked in agent PR #1743.

Desktop's Rust HTTP bridge treated any content type containing `xml` as UTF-8
text. The MIME types for PPTX, DOCX and XLSX contain `openxml`, but their files
are ZIP bytes. UI PR #611 matches actual text and structured JSON/XML types
instead, preserving Office responses as byte-exact base64.

UI PR #613 builds on that transport correction and automatically requests a PDF
when opening an Office artifact with no retained preview. Preview, download and
native PDF opening share one conversion per immutable artifact; reopening the
tab joins ongoing work. Saved PDFs are loaded immediately. Converter failures
remain visible with an explicit Retry control. Markdown, HTML and LaTeX keep
their direct views. The combined source pin is
`a47306f3737ca078fde6c07d8c56a82bbdcebcbc`.
Its math review example also distinguishes a rendered inline formula from plain
code notation and explicitly labelled TeX source; renderer code remains unchanged.

UI PR #614 keeps an agent-response sign-in dialog mounted while its verified
connection owner is rechecked in the background. Previously that refresh
unmounted the dialog and aborted its private OAuth return listener. A completed
owner mismatch or failed check still closes sign-in. Native lifecycle logs now
record only a phase, port and timestamp; callback URLs and credentials are never
logged. Regression cases cover refresh continuity and an owner change. This is
a confirmed source defect, but the user's particular Google return failure has
not been traced to that dialog. The supplied port was closed when inspected and
the local app log ended in a clean shutdown without a matching sign-in request.

UI PR #615 preserves the first tool block's identity and sequence when a live
result arrives. The OPAL export's consumed steering message correctly pointed
to that call, but the UI replaced its ID and could not place the user's question
before the following reply. The TypeScript UI reducer now matches the server's
saved-message projection; tool entities continue to receive output/state updates.
This does not change the clio-core repository or installed Core package.

Hosted preview qualification also caught refresh restarting an already successful
conversion. PR #613 now retains the immutable PDF query while refreshing content
and metadata. Its desktop/phone one-conversion assertions remain intact.

The combined pin also retains merged UI #612 from develop (`97f62670`), including
Obsidian management in Settings, vault creation/attachment choices and optional
managed Sync. The older installed Settings page lists browser accounts only,
which explains why the user's Attach screenshot shows Obsidian while Settings
does not. The corresponding managed-client backend is owned by agent PR #1745;
require that merge before this pin and preserve its independently owned worktree.

The final beta source pin also includes PDF fit/zoom #616, the unified HTML
Preview/Source toolbar #617, composable Carousel/Video #619, todo alignment #620,
compact model-aware search #621, global search #622, AmSC branding #623 and the
expandable ALCF inference server group #624. It preserves Obsidian #612/#618 and
all intervening develop additions. Agent #1745 is merged; its UI gitlink is an
ancestor of this combined pin.

Focused static and hosted results, actual live actions and deferred checks are
recorded separately in the campaign evidence. On 2026-10-14 the user explicitly
authorized merging and releasing this beta without waiting for CI or remaining
live acceptance, so they can test it. This pin does not claim that pending checks
passed. It does not rewrite the existing export, regenerate the OPAL deck or
establish visual review. Installed Core/app versions remain unchanged by the
source merge; the beta release is a separate published candidate.