# An orb's size is a Blazar reservation with an unlimited end

For each orb the service creates, with the consumer's token, a Blazar lease of type `virtual:instance` with the requested processors, memory and disk, a start of "now" and an end date very far away. For that reservation Blazar creates a non-public flavor, makes it accessible only to the consumer's project and, when the lease is deleted, destroys the machines that use it, waits until they no longer exist and deletes the flavor.

This way the tailored size requires no privileges from the service, and the flavor is deleted in the right order without a cleaner of our own. Blazar is used here for capacity and flavor, not for time ([0003](0003-no-expiry.md)).

## Rejected alternatives

**A private flavor created by the service** for each orb, the design of commit `eb7ee88`. Creating a flavor and granting access to it are operations reserved to the administrator in Nova's default policy, so the service would have needed an administrative credential, and a cleaner of its own to delete the flavor only after the machine, because Nova advises against deleting a flavor in use. Blazar does both with its own credentials and its own code.

**A catalog of fixed flavors**, with the size rounded to the nearest one. No privileges and no extra component, but rounding changes the requested size and couples each client to the flavor catalog.

**The flavor inside the template**, with `OS::Nova::Flavor`: Heat itself warns that the resource is usable only by administrators, and the stack is created with the consumer's token.

## Accepted consequences

- **Lease lifetime.** Blazar's required end date implements [0003](0003-no-expiry.md), not a client-visible expiry. The installation must allow that lease duration; see [installation requirements](../architecture.md#installation).
- **Activation before building.** Flavor access follows reservation activation, not lease creation. [0005](0005-lease-beside-the-stack.md) owns the required wait and the choice to keep the lease outside Heat.
- **Capacity checked before acceptance.** The [API contract](../design/api.md#error-codes) defines how a refused reservation differs from a later build failure.
- **Additional dependency.** The deployment needs Blazar and registered compute capacity, as described in [installation](../architecture.md#installation).

## Sources

- Creation of the non-public flavor for the reservation, project access in `on_start`, deletion of the machines and then of the flavor in `on_end`: <https://opendev.org/openstack/blazar/src/branch/master/blazar/plugins/instances/instance_plugin.py>
- `delete_lease` runs `on_end` on an active lease too; `start_date` accepts `now`: <https://opendev.org/openstack/blazar/src/branch/master/blazar/manager/service.py>
- Blazar policies, `blazar:leases:post` and `:delete` are `rule:project_member_or_admin`: <https://docs.openstack.org/blazar/latest/configuration/blazar-policy.html>
- `max_lease_duration`, default `-1`, that is no limit: <https://docs.openstack.org/blazar/latest/configuration/blazar-conf.html>
- Instance reservation procedure and host registration: <https://docs.openstack.org/blazar/latest/cli/instance-reservation.html>
- Nova's default policies on flavors, `rule:context_is_admin`: <https://docs.openstack.org/nova/latest/configuration/policy.html>
- `OS::Nova::Flavor`, «limited to being used by administrators only»: <https://docs.openstack.org/heat/latest/template_guide/openstack.html#OS::Nova::Flavor>
