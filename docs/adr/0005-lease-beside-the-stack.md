# The lease is created before the stack and stays outside it

The service creates the Blazar lease by calling Blazar, waits for the reservation to become active, and only then creates the Heat stack, passing it the reservation's flavor. The lease is **not** a template resource, although Heat offers `OS::Blazar::Lease` and putting it inside would give a single object to create and delete.

The reason is the wait. Heat's resource considers the lease created as soon as Blazar responds, without waiting for the reservation to be active: its code defines no completion check. But the project can use the reservation's flavor only after activation, so a machine in the same stack would be created too early and would fail. Outside the stack the wait is ours, explicit and observable.

## Rejected alternative

**The lease as a template resource**, with the machine depending on it. A single owner and a single deletion, and Heat would delete the lease by itself after the machine. Rejected because it works only if activation precedes the machine's creation by chance. To be reconsidered if a future version of Heat waited for the reservation to be active.

## Accepted consequences

- Two objects per orb, lease and stack, linked in the service's table.
- Creation is a sequence with a wait in the middle, run after the `202` response by a task inside the `orbit-api` process, which uses the request's token kept in memory ([0002](0002-resources-in-the-users-project.md)). The status distinguishes "reserving" from "building".
- Deletion touches both: first the stack, then the lease. By deleting the lease Blazar destroys the machine anyway, so the order matters for Heat's cleanup, not for capacity.

## Sources

- `heat/engine/resources/openstack/blazar/lease.py`: defines `handle_create` but no `check_create_complete` — <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/blazar/lease.py>
- Project access to the flavor granted in `on_start`: <https://opendev.org/openstack/blazar/src/branch/master/blazar/plugins/instances/instance_plugin.py>
