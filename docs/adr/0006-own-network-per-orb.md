# Each orb has its own network and router

An orb's template creates, besides the machine and the surrounding resources, a network with its subnet and a router connected to the external network. The orb does not rely on an existing project network: it is born and dies with its own, together with the rest of the stack ([0001](0001-provisioning-delegated-to-heat.md)).

This way an orb is isolated at the network level too, not only by the firewall: it does not share the segment with other machines, not even those of the same project. It does not require a pre-existing project network, though the project still needs quota and access to the configured external network. Separate routers let orbs reuse the template's address range.

## Rejected alternatives

**A project network named in the configuration**, the initial design. In DevStack the `private` network belongs to the `demo` project, and Heat resolves the name with the requester's token: for any other project the network does not exist and the stack fails. The service would have worked for one project only.

**A network chosen by the client in the request**, with the configured value as default. A small change, but it shifts onto the client the job of having a network with a router to the outside, and the machine would share the network with the project's other machines.

**A shared network prepared by the administrator** for all projects. A single network to manage, but orbs of different users would sit on the same segment, protected only by the firewall.

## Accepted consequences

- **Per-orb network quota.** Each orb consumes a router and a security group. Existing project resources, including its default security group, count too. Available Blazar capacity therefore does not guarantee that Neutron quota permits a new orb. Inspect the project's live quota and usage rather than assuming a fixed concurrency limit; quota failures follow the [API's build-failure behavior](../design/api.md#error-codes).
- **Slightly longer creation**: network, subnet, router and interface precede the port and the external address, which can be associated only with a port reachable from the router.
- **The service no longer configures project networks**: only the external network remains, `[orbs] public_network`.

## Sources

- Neutron's quota options and defaults: <https://opendev.org/openstack/neutron/src/branch/master/neutron/conf/quota.py>
- The `default` security group counts towards the quota: the ML2 plugin tracks security groups with the `SecurityGroup` model and usage is counted as rows filtered only by `project_id`, without excluding `is_default`: <https://opendev.org/openstack/neutron/src/branch/master/neutron/plugins/ml2/plugin.py> (`tracked_resources`), <https://opendev.org/openstack/neutron/src/branch/master/neutron/quota/resource.py> (`TrackedResource.count_used`)
- Heat resources `OS::Neutron::Router` (`external_gateway_info.network`), `OS::Neutron::RouterInterface`, `OS::Neutron::Subnet`: <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/neutron>
