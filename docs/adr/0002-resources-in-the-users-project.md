# Orbs are born in the project of whoever requests them

The service creates the resources on behalf of the consumer, forwarding the token received in the request, instead of owning them in a service project of its own. This way the isolation between users and the cap on machines are enforced by OpenStack, not by our database: the project quota says "no" without the service having to count anything, and the user sees their orbs with the OpenStack commands they already know.

## Rejected alternative

**A single service project owning all orbs.** Simpler to configure, a single credential. Rejected because it moves into our database two things OpenStack already does: a resource belonging to a user, and the consumption limit. A breach of that database would become a confusion of ownership between different users.

## Accepted consequence

The user's token lasts about an hour, and that is enough: since an orb does not expire ([0003](0003-no-expiry.md)), every operation on the user's resources happens during one of their requests or in the seconds right after it. The only work that follows the response is waiting for the reservation and creating the stack ([0005](0005-lease-beside-the-stack.md)), and it uses the request's token kept in memory. The service keeps neither tokens nor delegations, and has no privileges of its own over users' resources.

The price is that interrupted work, for example by a service restart during the wait, is not resumed by itself: the orb ends up in `ERROR` on the next read, and the user deletes it and requests another.

## Sources

- The problem of deferred operations and the authorization model Heat adopts to solve it: <https://docs.openstack.org/heat/latest/admin/auth-model.html>
