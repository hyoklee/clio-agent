# R50: reviewed recovery and control boundaries

Base: core `33b7dcdf29e4ae8ba9be9e00925a9171e69caf28`, GACT
`0a4ca5d5915a0add61cd5048b742161092468481`, marketplace
`1a9b8d0337217950a2b44c303a8d22547d52d756`. Core includes develop
`9965667afd6981194705b160ab22a3e0b09a5158`; GACT includes main
`6ea4e15e4ac3b0160237810b2f11ed3d2311c6a0`. Native dependency pins are unchanged.

This corrects three concrete independent-review findings. It adds no execution
owner, scheduler, registry, driving loop or delivery authority.

- Astra P1: the existing conversation CoreRecovery operation retains the original
  publication callback and its context until recording and publication finish.
  Stop cancels its waiter, not recovery/publication custody. The session recording
  hold clears afterward; inference and finalization are not repeated.
- Astra P2: Question/native/external owners receive the trusted caller and validate
  control permission under the same Core lock that accepts cancellation. Rejected
  controls cannot close native admission or become provisional outage controls.
  Already-accepted cancellation retries retain their original intent.
- Claude P3: normal shutdown distinguishes local execution from a surviving provider
  job using original source/submission custody, including a provider reply in flight.
  Transfer observation joins its current step, retains late identity and genuine
  completed publication, and stops without creating a cancellation request.
  WorkEvidence records local retirement separately from remote cleanup; matching
  incarnation receipts permit resource retirement, not terminal Download success.
  The existing ProviderContinuation path handles these receipts on memory and
  persistent backends. Normal closing reattachment callbacks retire; accepted
  explicit cancellation retains its cleanup continuation.

Native shutdown functions now reside with the existing physical-settlement
algorithms and remain methods of the same NativeTools owner. There is no new
shutdown coordinator. Core input commitment and notification acknowledgement are
unchanged. The static removal guard remains authoritative.

Fresh regression cases are constructed for cancelled recording waiters, shutdown,
revocation at each owner (including a recording hold), provider sleep/in-flight
reply/status error/publication/explicit cancellation, and stale incarnation receipts.
Provider response doubles are confined to tests; they do not qualify live Globus.
The legacy migration assertion compares canonical snapshots rather than the fixture's
pre-persistence object. The route fingerprint is measured: 387 unique pairs.

R49 actual Codex/Luna evidence on the recorded base demonstrates common native
handles/parallel work/observation/expired and final waits/result collection, plus
idle and post-Stop Question answer wakes. It does not qualify these corrections or
complete the full Q/R matrix. Current regression migration, final CI, real provider
recovery, capacity, workflows and integrated UI gates remain required.

No release/install/auth/default/released-pin changes. Protected human documents and
all exact rejected-removal/manual-only roots remain untouched. Generated state and
execution stay inside the D qualification repository.
