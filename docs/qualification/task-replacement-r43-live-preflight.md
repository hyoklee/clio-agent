# R43 live source attempt

Core `6f494f5f28c3a0bcbd750b4bee88e5ec683c9c2b`, GACT
`faddba474961c7499f1b57226af43c21de142a73`, marketplace
`43af7a011805ce55c63da4d49cc04b652af5dcf8`.

The production Windows source service started with Python 3.14.6/Core 2.3.1
and isolated state under the D qualification repository. API port 18835,
private Core base port 24125, service PID 48872. Authentication used an isolated
access-token copy with refresh disabled; installed credentials were not changed.

Workspace/session creation and blueprint installation succeeded. Selecting the
installed blueprint returned HTTP 500: `blueprint_selection.py` still called
removed `TurnRunner.reservation` and `request_input_admission` methods. Session
`sess_0f79d759c5ae` had no task snapshots and no model input. No model ran and no
Shell task was submitted. This attempt qualifies no Q/R row.

The service exited normally after a harness marker requested Uvicorn shutdown.
The service process and its private API/Core listeners were verified absent.
Other Core daemons were preserved. A bounded source correction is required in
the existing TurnRunner session reservation owner; the obsolete calls must be
removed rather than bypassing blueprint selection in the harness.
