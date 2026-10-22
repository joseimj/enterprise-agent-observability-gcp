/* ServiceNow scoped Script Include: AgentIncidentService (server-side only).
 * REQUIRED: incident.u_agent_dedupe_key STRING UNIQUE index; incident.u_agent_payload_hash
 * STRING; incident.u_agent_tenant STRING; custom x_oai_agent_tenant_access table
 * with u_user (reference sys_user), u_tenant (string), u_active (boolean).
 * A unique database index on u_agent_dedupe_key is MANDATORY: query-before-insert
 * alone is racy and does not prevent duplicate incidents.
 * Review cross-scope access, domain separation, ACL, and Business Rules before deployment.
 */
var AgentIncidentService = Class.create();
AgentIncidentService.prototype = {
  initialize: function () {},
  allowed: function (tenant) {
    if (!gs.hasRole('x_oai_agent.api_executor')) return false;
    var a = new GlideRecord('x_oai_agent_tenant_access');
    a.addQuery('u_user', gs.getUserID()); a.addQuery('u_tenant', tenant);
    a.addQuery('u_active', true); a.setLimit(1); a.query();
    return a.next();
  },
  getByKey: function (tenant, key) {
    var dedupe = tenant + ':' + key;
    var gr = new GlideRecord('incident');
    gr.addQuery('u_agent_dedupe_key', dedupe); gr.setLimit(1); gr.query();
    if (!gr.next()) return null;
    return {sys_id: String(gr.getUniqueValue()), number: String(gr.getValue('number')),
      payload_hash: String(gr.getValue('u_agent_payload_hash'))};
  },
  create: function (tenant, key, fingerprint, shortDescription, description) {
    var existing = this.getByKey(tenant, key);
    if (existing) return {conflict: existing.payload_hash !== fingerprint, incident: existing};
    var incident = new GlideRecord('incident'); incident.initialize();
    incident.setValue('short_description', shortDescription);
    incident.setValue('description', description);
    incident.setValue('u_agent_tenant', tenant);
    incident.setValue('u_agent_dedupe_key', tenant + ':' + key);
    incident.setValue('u_agent_payload_hash', fingerprint);
    var sysId = incident.insert();
    if (!sysId) {
      // A racing writer may have committed. Resolve using UNIQUE key; otherwise
      // return an uncertain error, not an automatic retry or a second insert.
      existing = this.getByKey(tenant, key);
      if (existing) return {conflict: existing.payload_hash !== fingerprint, incident: existing};
      throw new Error('Incident insert unconfirmed; operator reconciliation required');
    }
    existing = this.getByKey(tenant, key);
    if (!existing) throw new Error('Post-insert lookup unavailable');
    return {conflict: false, incident: existing};
  },
  type: 'AgentIncidentService'
};
