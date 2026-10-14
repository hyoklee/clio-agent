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
`379bc13e5d2084f146f714cc638dd11c77341b6c`.

New loopback HTTP regression cases cover the three OOXML types, case and MIME
parameters, and retained UTF-8 text behavior. Rustfmt was applied; local tests,
application builds/reloads and model inference were not run. Hosted qualification
is required before merging UI #611, then #613, then this agent source pin. The
combined UI tree includes both fixes so their hosted checks can run in parallel
with the agent pin. Agent #1743 separately corrects Windows renderer access.
This change
does not rewrite the existing export, regenerate the deck, or establish visual
review. The installed app retains its earlier source revision until a later
authorized rebuild.
