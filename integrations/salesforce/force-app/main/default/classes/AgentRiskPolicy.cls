public with sharing class AgentRiskPolicy {
    public class PolicyException extends Exception {}
    public static void validateAccountId(String accountId) {
        if (String.isBlank(accountId) || !Pattern.matches('[a-zA-Z0-9]{15,18}', accountId)) {
            throw new PolicyException('Invalid Salesforce account ID');
        }
    }
    public static Account readAccount(Id accountId) {
        List<Account> records = [SELECT Id, Name, Industry, Type FROM Account
            WHERE Id = :accountId WITH USER_MODE LIMIT 1];
        if (records.isEmpty()) throw new PolicyException('Account unavailable');
        return records[0];
    }
}
