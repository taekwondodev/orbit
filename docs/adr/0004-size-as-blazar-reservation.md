# An orb's size is a Blazar reservation with an unlimited end

For each orb the service creates, with the consumer's token, a Blazar lease of type `virtual:instance` with the requested processors, memory and disk, a start of "now" and an end date very far away. For that reservation Blazar creates a non-public flavor, makes it accessible only to the consumer's project and, when the lease is deleted, destroys the machines that use it, waits until they no longer exist and deletes the flavor.

This way the tailored size requires no privileges from the service, and the flavor is deleted in the right order without a cleaner of our own. Blazar is used here for capacity and flavor, not for time ([0003](0003-no-expiry.md)).

## Rejected alternatives

**A private flavor created by the service** for each orb, the design of commit `eb7ee88`. Creating a flavor and granting access to it are operations reserved to the administrator in Nova's default policy, so the service would have needed an administrative credential, and a cleaner of its own to delete the flavor only after the machine, because Nova advises against deleting a flavor in use. Blazar does both with its own credentials and its own code.

**A catalog of fixed flavors**, with the size rounded to the nearest one. No privileges and no extra component, but it betrays the "every orb with different resources" requirement.

**The flavor inside the template**, with `OS::Nova::Flavor`: Heat itself warns that the resource is usable only by administrators, and the stack is created with the consumer's token.

## Accepted consequences

- **Fictitious end date.** Blazar requires an end; the service sets it to a configured value very far away. Blazar places no limit on the duration as long as `max_lease_duration` stays at its default `-1`: the installation must leave it that way.
- **Wait before building.** The flavor exists from the lease's creation, but the project can access it only when the reservation becomes active, that is at the next round of Blazar's event loop, which runs every ten seconds. The stack is created afterwards: the orb has a `RESERVING` status distinct from `BUILDING`.
- **Capacity checked right away.** If no host has room for the size, Blazar rejects the creation of the lease: the orb fails before anything is built.
- **Heavier installation.** The `blazar`, `blazar-nova` and `python-blazarclient` packages are needed, and no lease can be created until the compute host has been registered in Blazar (`openstack reservation host create <host>`): the registration goes into the installation plugin.

## Sources

- Creation of the non-public flavor for the reservation, project access in `on_start`, deletion of the machines and then of the flavor in `on_end`: <https://opendev.org/openstack/blazar/src/branch/master/blazar/plugins/instances/instance_plugin.py>
- `delete_lease` runs `on_end` on an active lease too; `start_date` accepts `now`; event loop every 10 seconds (`EVENT_INTERVAL`): <https://opendev.org/openstack/blazar/src/branch/master/blazar/manager/service.py>
- Blazar policies, `blazar:leases:post` and `:delete` are `rule:project_member_or_admin`: <https://docs.openstack.org/blazar/latest/configuration/blazar-policy.html>
- `max_lease_duration`, default `-1`, that is no limit: <https://docs.openstack.org/blazar/latest/configuration/blazar-conf.html>
- Instance reservation procedure and host registration: <https://docs.openstack.org/blazar/latest/cli/instance-reservation.html>
- Nova's default policies on flavors, `rule:context_is_admin`: <https://docs.openstack.org/nova/latest/configuration/policy.html>
- `OS::Nova::Flavor`, «limited to being used by administrators only»: <https://docs.openstack.org/heat/latest/template_guide/openstack.html#OS::Nova::Flavor>
