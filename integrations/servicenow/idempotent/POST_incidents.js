/* Scripted REST API resource: POST /incidents.
 * REST API name/path sample: /api/x_oai_agent/v1/incidents
 * Require ServiceNow OAuth and role-based scripted API security.
 * Does not trust tenant_id from request without authenticated membership lookup.
 */
(function process(request, response) {
  var body = request.body.data || {};
  var tenant = body.tenant_id, key = body.action_key;
  var summary = body.short_description, description = body.description;
  if (typeof tenant !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(tenant) ||
      typeof key !== 'string' || !/^[A-Za-z0-9_.:-]{8,128}$/.test(key) ||
      typeof summary !== 'string' || summary.length < 1 || summary.length > 160 ||
      typeof description !== 'string' || description.length < 1 || description.length > 4000) {
    response.setStatus(400); response.setBody({error: 'Invalid request'}); return;
  }
  var svc = new AgentIncidentService();
  if (!svc.allowed(tenant)) { response.setStatus(403); response.setBody({error:'Forbidden'}); return; }
  // Store canonical field composition instead of a weak non-cryptographic hash.
  // GlideDigest SHA256 applies to the exact field sequence; separator avoids ambiguity.
  var canonical = JSON.stringify([tenant, key, summary, description]);
  var fingerprint = new GlideDigest().getSHA256Hex(canonical);
  try {
    var outcome = svc.create(tenant, key, fingerprint, summary, description);
    if (outcome.conflict) {response.setStatus(409); response.setBody({result:{error:'Key reused with different payload'}}); return;}
    response.setStatus(200);
    response.setBody({result:{sys_id:outcome.incident.sys_id, number:outcome.incident.number,
      action_key:key, tenant_id:tenant}});
  } catch (e) {
    gs.error('Agent incident create outcome uncertain: ' + e.message);
    response.setStatus(503); response.setBody({error:'Outcome uncertain; reconcile by key'});
  }
})(request, response);
