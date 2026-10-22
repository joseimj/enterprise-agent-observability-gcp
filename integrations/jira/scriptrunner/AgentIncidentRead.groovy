// ScriptRunner for Jira Cloud (Groovy). Execute as a ScriptRunner endpoint/script
// in an appropriately permissioned Jira Cloud environment. Not standalone Groovy.
// Adapt binding/endpoint wrapper to your installed ScriptRunner version.
import groovy.json.JsonOutput

def accountKey = (binding.hasVariable('accountKey') ? binding.getVariable('accountKey') : '') as String
if (!(accountKey ==~ /[A-Za-z0-9_-]{1,32}/)) {
    return JsonOutput.toJson([error: 'invalid_account_key'])
}
// ScriptRunner Cloud provides get() for authenticated Jira REST API calls.
// Never build JQL with unvalidated user input.
def jql = 'project = OPS AND labels = "account-' + accountKey + '" ORDER BY created DESC'
def result = get('/rest/api/3/search/jql')
    .queryString('jql', jql)
    .queryString('maxResults', '50')
    .queryString('fields', 'summary,status,priority,updated')
    .asObject(Map)
if (result.status != 200) {
    return JsonOutput.toJson([error: 'jira_query_failed', status: result.status])
}
def incidents = (result.body.issues ?: []).collect { issue ->
    [key: issue.key, summary: issue.fields?.summary,
     status: issue.fields?.status?.name,
     priority: issue.fields?.priority?.name]
}
return JsonOutput.toJson([account_key: accountKey, incidents: incidents])
