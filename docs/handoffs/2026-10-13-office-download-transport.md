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
`e61f8d779e206e82eb5bb1425e1f0e04cac4b378`.
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

New loopback HTTP regression cases cover the three OOXML types, case and MIME
parameters, and retained UTF-8 text behavior. Rustfmt was applied; local tests,
application builds/reloads and model inference were not run. Hosted qualification
is required before merging UI #611, then #613, then #614, then #615, then this agent source
pin. The combined UI tree includes these fixes so their hosted checks run in parallel
with the agent pin. Agent #1743 separately corrects Windows renderer access.
This change
does not rewrite the existing export, regenerate the deck, or establish visual
review. The installed app retains its earlier source revision until a later
authorized rebuild.
