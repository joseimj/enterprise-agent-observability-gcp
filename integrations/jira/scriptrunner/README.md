# Jira Groovy integration (ScriptRunner Cloud)

`AgentIncidentRead.groovy` is a **deployment template**, not a locally executable service.
It assumes ScriptRunner for Jira Cloud with its HTTP client helper `get()` and a configured
script/endpoint binding for `accountKey`. Validate the binding and endpoint mechanism against
your installed ScriptRunner version before deployment. It queries Jira REST API v3 and
projects only safe incident metadata. Jira permissions still apply.

**No write script is included.** Jira writes must use the audited Tool Gateway with a
validated approval token, idempotency key, and server-side authorization. Do not place
secrets or raw prompts in ScriptRunner logs. Use Jira native audit logging where available.
