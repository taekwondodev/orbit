# Heat creates the orb's resources, not the service's code

Describe the orb's resources in a Heat template rather than provisioning them through direct Nova and Neutron calls. The important trade-off is recovery: a later failure requires cleanup of earlier resources, and that cleanup can also fail. Heat owns dependency ordering and resource cleanup, so orbit does not need a second provisioning state machine.

The only resource outside the template is the Blazar lease: the reason is in [0005](0005-lease-beside-the-stack.md).

## Rejected alternative

**Direct orchestration with `openstacksdk`**, that is the service creating key, firewall, port and machine one call at a time. Rejected because it would have required writing, and proving correct, the recovery from partial failures and the retries. It is the choice with the most code of our own, and it is legitimate if the heart of the project is meant to be provisioning; here the heart is the orb as an object: reserved capacity, status faithful to reality, complete deletion.

## Accepted consequences

- New orb resources belong in the template, so Heat remains responsible for their dependencies and cleanup.
- Stack creation is asynchronous. orbit observes it through [reconciliation](../design/state.md#reconciliation), rather than treating acceptance of the stack request as readiness.
- Deployments must provide Heat. DevStack plugin ordering and installation requirements belong to [architecture](../architecture.md#installation).

## Sources

- DevStack plugin contract and `stack.sh` phases: <https://docs.openstack.org/devstack/latest/plugins.html>
- Enabling Heat on DevStack (`enable_plugin heat https://opendev.org/openstack/heat`): <https://docs.openstack.org/heat/latest/getting_started/on_devstack.html>
