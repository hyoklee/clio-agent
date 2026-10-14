# Office artifact transport in session exports

The user's `D:/Libraries/Downloads/OPAL-1.transcript.html` (SHA-256
`f064768257db00a3636ea6ceeaa7a653f4782ddd5e36231b1cef263aa73c7111`)
records a snapshot failure for the published PowerPoint artifact:
`gact_http_response_unreadable: decode text body: invalid utf-8 sequence`.
This is separate from the rendering failure tracked in agent PR #1743.

Desktop's Rust HTTP bridge treated any content type containing `xml` as UTF-8
text. The MIME types for PPTX, DOCX and XLSX contain `openxml`, but their files
are ZIP bytes. UI PR #611 matches actual text and structured JSON/XML types
instead, preserving Office responses as byte-exact base64. The source pin is
`dc092e84c05a4f7222c5e416a95ac2b9fe858435`.

New loopback HTTP regression cases cover the three OOXML types, case and MIME
parameters, and retained UTF-8 text behavior. Rustfmt was applied; local tests,
application builds/reloads and model inference were not run. Hosted qualification
is required before merging the UI and then its agent source pin. This change
does not rewrite the existing export, regenerate the deck, or establish visual
review. The installed app retains its earlier source revision until a later
authorized rebuild.
