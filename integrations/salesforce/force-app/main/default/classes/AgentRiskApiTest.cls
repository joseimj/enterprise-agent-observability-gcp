@IsTest
private class AgentRiskApiTest {
    @IsTest static void rejectsInvalidId() {
        RestRequest req = new RestRequest();
        req.requestURI = '/services/apexrest/agent-risk/v1/accounts/invalid';
        req.httpMethod = 'GET';
        RestContext.request = req;
        RestContext.response = new RestResponse();
        Test.startTest();
        AgentRiskApi.getAccountRiskContext();
        Test.stopTest();
        System.assertEquals(400, RestContext.response.statusCode);
    }
    @IsTest static void returnsAccount() {
        Account a = new Account(Name='ACME Lab'); insert a;
        RestRequest req = new RestRequest();
        req.requestURI = '/services/apexrest/agent-risk/v1/accounts/' + a.Id;
        req.httpMethod = 'GET';
        RestContext.request = req;
        RestContext.response = new RestResponse();
        Test.startTest();
        AgentRiskApi.getAccountRiskContext();
        Test.stopTest();
        System.assertEquals('ACME Lab',
            ((Map<String,Object>) JSON.deserializeUntyped(RestContext.response.responseBody.toString())).get('name'));
    }
}
