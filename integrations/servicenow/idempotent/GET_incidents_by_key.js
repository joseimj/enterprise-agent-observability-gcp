/* Scripted REST API resource: GET /incidents/{tenant_id}/{action_key}
 * Define path params tenant_id and action_key on resource.
 */
(function process(request, response) {
  var tenant = request.pathParams.tenant_id, key = request.pathParams.action_key;
  if (typeof tenant !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(tenant) ||
      typeof key !== 'string' || !/^[A-Za-z0-9_.:-]{8,128}$/.test(key)) {
    response.setStatus(400); response.setBody({error:'Invalid request'}); return;
  }
  var svc = new AgentIncidentService();
  if (!svc.allowed(tenant)) {response.setStatus(403); response.setBody({error:'Forbidden'}); return;}
  var incident = svc.getByKey(tenant, key);
  if (!incident) {response.setStatus(404); response.setBody({error:'Not found'}); return;}
  response.setStatus(200);
  response.setBody({result:{sys_id:incident.sys_id, number:incident.number,
    action_key:key, tenant_id:tenant}});
})(request, response);
