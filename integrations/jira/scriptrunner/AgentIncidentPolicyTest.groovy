import groovy.test.GroovyTestCase
class AgentIncidentPolicyTest extends GroovyTestCase {
    void testApprovedTransition() {
        assert AgentIncidentPolicy.canPropose('OPS-101', 'Escalate', true)
    }
    void testDeniedWithoutApproval() {
        assert !AgentIncidentPolicy.canPropose('OPS-101', 'Escalate', false)
        assert !AgentIncidentPolicy.canPropose('OPS-101', 'Delete', true)
    }
}
