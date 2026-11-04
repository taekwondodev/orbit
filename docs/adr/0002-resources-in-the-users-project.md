# Orbs are born in the project of whoever requests them

The service creates the resources on behalf of the consumer, forwarding the token received in the request, instead of owning them in a service project of its own. This way project isolation and resource quotas are enforced by OpenStack, not by our database: the project quota says "no" without the service having to count anything, and the user sees their orbs with the OpenStack commands they already know.

## Rejected alternative

**A single service project owning all orbs.** Simpler to configure, a single credential. Rejected because it moves into our database two things OpenStack already does: a resource belonging to a user, and the consumption limit. A breach of that database would become a confusion of ownership between different projects.

## Accepted consequence

The service persists neither tokens nor delegations and has no privileges of its own over users' resources. Request work and the bounded creation task use the request's token in memory. Its remaining lifetime is controlled by Keystone, not orbit: a short-lived token can expire before creation finishes. Surviving that expiry or a process restart would require a different authorization model, not merely a longer timeout. The background task and deadlines are described in [reconciliation](../design/state.md#reconciliation).

The price is that a restart does not resume the creation task. Reads can still observe surviving resources; [reconciliation](../design/state.md#reconciliation) owns the recovery and interrupted-creation rules. The consumer remains responsible for deleting resources left by unsuccessful work.

## Sources

- The problem of deferred operations and the authorization model Heat adopts to solve it: <https://docs.openstack.org/heat/latest/admin/auth-model.html>
