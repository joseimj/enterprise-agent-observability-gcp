// Scripted REST Resource: GET /api/x_your_scope/agent-risk/v1/context/{account_ref}
// Bind an explicit API ACL/role and OAuth identity in ServiceNow before deployment.
(function process(request, response) {
    var ref = String(request.pathParams.account_ref || '');
    try {
        var result = new AgentRiskService().readContext(ref);
        response.setStatus(200);
        response.setBody(result);
    } catch (e) {
        response.setStatus(400);
        response.setBody({error: 'invalid_request'});
    }
})(request, response);
