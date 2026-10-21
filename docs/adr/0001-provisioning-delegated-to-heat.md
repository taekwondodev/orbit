# Heat creates the orb's resources, not the service's code

The service does not call Nova and Neutron to build an orb: it describes the resources in a Heat template and asks Heat to create a stack from it. The reason is not the amount of code saved, but the hard case: creating an orb is four operations in a row, and when the third fails the first two must be undone knowing that the undoing can fail too. It is the point where hand-written provisioning leaves running machines that nobody deletes anymore, and Heat has solved it for years.

The only resource outside the template is the Blazar lease: the reason is in [0005](0005-lease-beside-the-stack.md).

## Rejected alternative

**Direct orchestration with `openstacksdk`**, that is the service creating key, firewall, port and machine one call at a time. Rejected because it would have required writing, and proving correct, the recovery from partial failures and the retries. It is the choice with the most code of our own, and it is legitimate if the heart of the project is meant to be provisioning; here the heart is the orb as an object: reserved capacity, status faithful to reality, complete deletion.

## Accepted consequences

- Provisioning disappears from the project: what remains is a template of a few dozen lines.
- Heat creates the stack asynchronously and exposes its status: the service does not wait for the build, it discovers it by reading the stack when someone asks about the orb.
- Heat must be enabled in the installation: it is not part of the default set and is added as a plugin, starting the `h-eng`, `h-api` and `h-api-cfn` processes.

## Sources

- DevStack plugin contract and `stack.sh` phases: <https://docs.openstack.org/devstack/latest/plugins.html>
- Enabling Heat on DevStack (`enable_plugin heat https://opendev.org/openstack/heat`): <https://docs.openstack.org/heat/latest/getting_started/on_devstack.html>
