# Each orb has its own network and router

An orb's template creates, besides the machine and the surrounding resources, a network with its subnet and a router connected to the external network. The orb does not rely on an existing project network: it is born and dies with its own, together with the rest of the stack ([0001](0001-provisioning-delegated-to-heat.md)).

This way an orb is isolated at the network level too, not only by the firewall: it does not share the segment with other machines, not even those of the same project. And it works in any project without preparation, because it does not depend on a network the project must already have. All orbs use the same address range, each behind its own router.

## Rejected alternatives

**A project network named in the configuration**, the initial design. In DevStack the `private` network belongs to the `demo` project, and Heat resolves the name with the requester's token: for any other project the network does not exist and the stack fails. The service would have worked for one project only.

**A network chosen by the client in the request**, with the configured value as default. A small change, but it shifts onto the client the job of having a network with a router to the outside, and the machine would share the network with the project's other machines.

**A shared network prepared by the administrator** for all projects. A single network to manage, but orbs of different users would sit on the same segment, protected only by the firewall.

## Accepted consequences

- **One router per orb, and therefore a cap per project.** By default Neutron limits each project to 10 routers and 10 security groups; each orb uses one of each, and the project's `default` security group counts towards the quota. With the default values a project holds about 9 concurrent orbs. These are per-project quotas and the administrator raises them at will, for example with `openstack quota set --routers 50 --secgroups 50 <project>`. When a quota is exhausted, Heat rejects the stack and the orb goes to `ERROR` with Neutron's reason ([0002](0002-resources-in-the-users-project.md)).
- **Slightly longer creation**: network, subnet, router and interface precede the port and the external address, which can be associated only with a port reachable from the router.
- **The service no longer configures project networks**: only the external network remains, `[orbs] public_network`.

## Sources

- Neutron's default quotas, `DEFAULT_QUOTA_ROUTER = 10` and `DEFAULT_QUOTA_SG = 10`: <https://opendev.org/openstack/neutron/src/branch/master/neutron/conf/quota.py>
- The `default` security group counts towards the quota: the ML2 plugin tracks security groups with the `SecurityGroup` model and usage is counted as rows filtered only by `project_id`, without excluding `is_default`: <https://opendev.org/openstack/neutron/src/branch/master/neutron/plugins/ml2/plugin.py> (`tracked_resources`), <https://opendev.org/openstack/neutron/src/branch/master/neutron/quota/resource.py> (`TrackedResource.count_used`)
- Heat resources `OS::Neutron::Router` (`external_gateway_info.network`), `OS::Neutron::RouterInterface`, `OS::Neutron::Subnet`: <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/neutron>
