# Review 9 corrections — not runtime acceptance

Parent: core `90a7db56ac782167859426bed5993fb8f523b841`; GACT remains
`f1b099cdf479a4e2516391a525efeba17799cd65`.

Both independent source reviews returned NO-GO. Their recorded verdicts remain
in force until the corrected candidate is reviewed. No replacement-service
model, UI, final CI or release acceptance is claimed here.

## Corrections

- Rebuild the missing A2UI Core-mail producer and derive its consumed display
  state from recipient-input commitment. Retry the same received action identity.
  Restore the retained resource capability/deletion helpers omitted during removal.
- Use Linux boot ID and `/proc/<pid>/stat` start ticks, rather than an unsupported
  public psutil argument. Legacy incomplete identity remains uncertain.
- Retry native cancellation after adoption/restoration against its immutable
  submission/task identity; distinguish a withdrawn body from failed execution.
  Begin native shutdown cancellation before waiting for unresolved conversations.
- Cancel subtree members concurrently with parent retirement. Preserve the frozen
  membership, retry failed requests, and require actual retirement and cleanup.
  Restore cancellation before interpreting pause state.
- Retain predecessor cleanup evidence for the existing Core recovery callback.
- Decode historical ownership from the Core segment envelope. Retain malformed
  rows individually, keep uncertainty visible, and coalesce replay wake hints.
- Resolve authorized aliases before wait/observe registration; uncertainty ends
  waiting even when an older record lacks an attention episode.
- Repair stored-session dictionary access and workflow metadata updates.
- Serialize external input lookup, ignore unrelated unconfirmed sibling adoption,
  and retain raw cancelled external replies separately from physical settlement.
- Preserve a draft Question's original deadline on retry. Correct Question cancel
  acknowledgements and HTTP alias/grant errors.
- Keep transient Globus status responses pending in the existing workload loop;
  check cancellation before provider submission.

## Review adjudication

Astra's focused follow-up retained the R2 rule: external acknowledgement alone
does not prove physical cleanup. The implementation therefore preserves visible
uncertainty, prevents unsafe successors, and cancels native work before draining
unresolved external controls. No generic external cleanup protocol or automatic
shutdown cutoff was added. The pinned Pydantic ValidationError inherits ValueError;
the contrary tentative review finding did not require a new exception policy.

## Evidence limits

The frozen-parent fresh batch had 30 passes and 19 failed/setup-error cases.
Eleven failures used invalid newly authored owner fixtures. Five exposed the
application import defect; two exposed migration decoding; one exposed stored
session access. These are recorded failures, not accepted exclusions.

On the correction source: scoped Ruff/format, Mypy for 18 production files,
application import without lifespan/model startup, and the removal guard passed.
Fresh corrected behavioral execution, independent rereview, exact-head CI,
Q1–Q9 and final R1–R6 repetitions remain pending.

The changes extend existing owners, the Core writer and SDK observer. They add
no scheduler, execution registry, alternative mailbox or external cleanup proof.
