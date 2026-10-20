# Analyze streams and available history

The agent owns discovery, acquisition, continuation and analysis. For a scientific
question, execute the approved workflow and return the evidence and interpretation.
Describe interface controls only when the user asks how to operate them. A required
approval or private login is a handoff; reading a public sample or using a returned
continuation value is normally the agent's work.

## Establish what is being delivered

Inspect the selected catalog/resource metadata, provider documentation and actual
payload. Establish the producing instrument or model, variable meanings and units,
time encoding, reference frame and documented processing. Distinguish:

- Measured observations with a traceable acquisition source.
- Derived or preprocessed observations with documented transformations.
- Simulation, synthetic/example data, and values whose origin is unverified.

Preprocessing can be appropriate for a research question; identify what changed
and whether the resulting variables support it. Do not call a catalog export
raw measurements based on its filename, or infer physical displacement from
columns named east/north/up without the required provenance, units and frame.

For a question about a physical phenomenon, unresolved observational provenance
is a limit on the scientific answer. Audit timestamps or bytes as needed to
diagnose the source, and seek documented observations through the available
catalog/services. Do not fill the answer with trends, percentile comparisons or
plots of provenance-unverified values as a substitute for the requested science.
Call them records or values, not observations/measurements. A numerical data audit
is a separate deliverable only when the user requests it or it is necessary to
explain the missing evidence; it does not complete the physical investigation.

SSE, Kafka and a CSV file describe delivery or storage. None proves authenticity,
live acquisition or historical retention. A CSV replay emits file rows; changing
its delivery interval does not acquire new observations. Never replace an
unavailable requested stream with a convenient replay URL and call that success.
An unrelated example can be offered as a separately labelled transport exercise.

## Find the historical coverage that actually exists

Inspect the requested service's advertised query, retention and continuation
capabilities. Use its documented time/offset bounds and measurement timestamps to
establish which history can be retrieved. The oldest record in a short sample is
not necessarily the oldest retained observation. A consumer's local memory buffer
is also not the upstream historical archive.

If the stream supplies no retrievable history, look for a corresponding NDP
archive when it is relevant to the question. Check that instrument, variables,
processing, units and reference frame are compatible. Keep the archive's identity
and coverage separate from the stream's; disclose any joined source or conversion.
Do not quietly substitute a different station, demonstration file or source.

Report the actual outcome:

| Finding | Scientific consequence |
| --- | --- |
| Requested history is available and compatible | Retrieve it and perform the comparison. State the verified dates and gaps. |
| Only a limited retention window is available | Analyze that window and state which requested periods it cannot cover. |
| The inspected service supplies current data only, with no compatible archive found | Say historical data is unavailable through those checked sources. Explain what a new bounded capture can answer. |
| Access, service failure or missing metadata prevents checking history | Say historical availability could not be verified, naming the actual obstacle. Do not claim the history does not exist. |
| Only demonstration, synthetic or provenance-unverified values are available | Do not use them as evidence about the physical phenomenon. State which provenance or observation source is missing. |

## Acquire, continue and analyze

Load `services-and-streams.md` for the selected service procedure. Use returned
identities, approved filters and bounded reads, and inspect the captured bytes.
Keep exact API cursors, partition/offset positions and source revisions with the
investigation. Reuse the service's own continuation contract and verify adjacent
measurement identities for repeats or gaps. A replay's row cursor and a broker's
retained offsets are not interchangeable.

Handle continuation internally when the user asks for the next segment. Ordinary
answers should describe the observations and available next action, not ask the
user to copy an opaque cursor or rerun a request. Show such details only if the
user requests diagnostics or a reproducible low-level example. If the completion
position is missing or ambiguous, explain that uncertainty before resuming.

Compute from the actually acquired interval and inspected variables. Check sample
counts, clocks, gaps, flags and uncertainty before aggregating or joining history.
Use the existing scientific analysis and interactive chart capabilities for useful
results. Present supported conclusions, provenance/processing, history coverage
and material limitations. Stop only producers owned by this investigation.

Successful transport, a replay continuity check, loading a skill or producing a
chart is not scientific task acceptance. Read the actual conversation and verify
that its evidence answers the user's question before describing the run as a
successful scientific demonstration.
