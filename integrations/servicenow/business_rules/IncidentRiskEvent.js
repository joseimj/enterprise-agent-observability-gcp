// After-update Business Rule on incident, only when material fields change.
// Use async execution/queue for outbound integration; do not block the transaction.
(function executeRule(current, previous) {
    if (!current.priority.changes() && !current.state.changes()) return;
    gs.eventQueue('x_your_scope.agent.incident.changed', current,
        String(current.getUniqueValue()), String(current.getValue('number')));
})(current, previous);
