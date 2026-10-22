/** ScriptRunner Jira Data Center helper: validate proposed transition before execution.
 * Cloud uses different ScriptRunner APIs; do not deploy this DC code to Cloud.
 */
class AgentIncidentPolicy {
    static final Set<String> ALLOWED_TRANSITIONS = ['Escalate', 'Investigate'] as Set
    static boolean canPropose(String issueKey, String transitionName, boolean approved) {
        return issueKey ==~ /[A-Z][A-Z0-9]+-[0-9]+/ &&
               ALLOWED_TRANSITIONS.contains(transitionName) && approved
    }
}
