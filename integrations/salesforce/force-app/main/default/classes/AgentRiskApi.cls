@RestResource(urlMapping='/agent-risk/v1/accounts/*')
global with sharing class AgentRiskApi {
    @HttpGet
    global static void getAccountRiskContext() {
        RestResponse response = RestContext.response;
        String path = RestContext.request.requestURI;
        String accountId = path.substring(path.lastIndexOf('/') + 1);
        if (!Pattern.matches('[a-zA-Z0-9]{15,18}', accountId)) {
            response.statusCode = 400;
            response.responseBody = Blob.valueOf('{"error":"invalid_account_id"}');
            return;
        }
        // WITH USER_MODE enforces sharing, CRUD, and FLS for this SOQL operation.
        List<Account> accounts = [SELECT Id, Name, Industry, Type FROM Account
                                  WHERE Id = :accountId WITH USER_MODE LIMIT 1];
        if (accounts.isEmpty()) {
            response.statusCode = 404;
            response.responseBody = Blob.valueOf('{"error":"not_found"}');
            return;
        }
        Account a = accounts[0];
        Map<String, Object> result = new Map<String, Object>{
            'account_id' => a.Id, 'name' => a.Name,
            'industry' => a.Industry, 'type' => a.Type
        };
        response.addHeader('Content-Type', 'application/json');
        response.responseBody = Blob.valueOf(JSON.serialize(result));
    }
}
