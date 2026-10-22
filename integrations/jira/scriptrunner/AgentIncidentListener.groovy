// Jira Data Center / ScriptRunner listener reference.
// Event binding and injected issue object are configured in ScriptRunner UI.
// No outbound writes here; send a minimal event to an approved queue/webhook
// using managed secrets, with retries and deduplication outside this listener.
String key = issue?.key
if (key && key ==~ /[A-Z][A-Z0-9]+-[0-9]+/) {
    log.info('agent_audit issue_changed issue_key={} event_type=issue_updated', key)
}
