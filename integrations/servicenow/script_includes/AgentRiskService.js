// Scoped Script Include. Configure caller access, application scope and ACLs in your instance.
var AgentRiskService = Class.create();
AgentRiskService.prototype = {
    initialize: function () {},
    readContext: function (accountRef) {
        if (!/^[A-Za-z0-9_-]{1,32}$/.test(accountRef || ''))
            throw new Error('Invalid account reference');
        var incidents = [];
        var gr = new GlideRecordSecure('incident');
        gr.addQuery('u_customer_reference', accountRef); // Requires a configured custom field.
        gr.setLimit(50);
        gr.query();
        while (gr.next()) {
            incidents.push({
                number: String(gr.getValue('number')),
                state: String(gr.getValue('state')),
                priority: String(gr.getValue('priority')),
                configuration_item: String(gr.getDisplayValue('cmdb_ci'))
            });
        }
        return {account_id: accountRef, incidents: incidents};
    },
    type: 'AgentRiskService'
};
