# ServiceNow integration (instance deployment required)

The Script Include uses `GlideRecordSecure` and limits results. Configure the custom
`incident.u_customer_reference` field, an application scope, REST route, OAuth client,
role-based ACLs and event registration before installing. Never rely on caller-supplied
identity headers. The Business Rule queues an event rather than invoking an external
service in the incident transaction. Use ServiceNow ATF for authorization, pagination,
ACL and incident state-change tests. These scripts are **deployment examples**, not
validated against a live ServiceNow instance.
