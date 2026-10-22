@IsTest private class AgentRiskPolicyTest {
    @IsTest static void invalidIdRejected() {
        try {
            AgentRiskPolicy.validateAccountId('bad');
            System.assert(false, 'Expected invalid ID to be rejected');
        } catch (AgentRiskPolicy.PolicyException expected) {
            System.assert(expected.getMessage().contains('Invalid'));
        }
    }
    @IsTest static void validIdAccepted() {
        AgentRiskPolicy.validateAccountId('001000000000000AAA');
    }
}
