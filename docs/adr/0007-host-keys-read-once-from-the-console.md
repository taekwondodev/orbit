# The orb's SSH host keys are read once from the console and stored

When an orb's machine has booted, the service reads its SSH host keys from the Nova console and stores them in the `orbs` table; the API returns them as `ssh_host_keys` so that the client connects with strict host key checking. The keys belong to the machine, so storing them is an exception to [stored state](../design/state.md)'s "we store only what we own". The reason is that the console is not a reliable owner. Nova returns only its last part (100 KiB with libvirt), so the boot block scrolls out on a chatty orb. A root process inside the orb can also print a forged block later. Only the first block, printed at boot while only the image's code runs, is trusted, and it is read once, within `ready_timeout` of the creation request: a block that appears later may come from inside the orb.

The block is the one both cloud-init (`keys_to_console`) and CirrOS (`cirros-status`) print. It appears once the client's key is installed and sshd answers, so it is also the readiness signal: an orb is `ACTIVE` only once its keys are stored ([reconciliation](../design/state.md#reconciliation)). The console is read with `POST /servers/{id}/action` (`os-getConsoleOutput`), which changes nothing in Nova, under the project member's default policy and the requester's token ([0002](0002-resources-in-the-users-project.md)).

## Rejected alternatives

**Reading the console on every read, storing nothing.** The table would keep only what it owns, but the keys would disappear after 100 KiB of console and could be replaced from inside the orb.

**A Heat WaitCondition**, signalled by cloud-init with the keys and exposed as a stack output. Heat would own the data and the stack would complete only once sshd is ready. Rejected because the machine would have to reach Heat's API from its own network ([0006](0006-own-network-per-orb.md)), the signal would travel over the network, and the WaitCondition's token would sit in the orb's metadata, readable by the agent inside.

## Accepted consequences

- An image that prints no block never becomes `ACTIVE`: its orbs end in `ERROR` after `ready_timeout`.
- `ready_timeout` counts from the creation request, so it includes the wait for the reservation and the stack and must be greater than `creation_timeout`.

## Sources

- cloud-init's `write-ssh-key-fingerprints`, called by `cc_keys_to_console`: <https://github.com/canonical/cloud-init/blob/main/tools/write-ssh-key-fingerprints>
- CirrOS's `cirros-status`: <https://github.com/cirros-dev/cirros/blob/main/src/sbin/cirros-status>
- Nova's console limit, `MAX_CONSOLE_BYTES = 100 * units.Ki`: <https://opendev.org/openstack/nova/src/branch/master/nova/virt/libvirt/driver.py>
- Nova's console policy, `os_compute_api:os-console-output` with `PROJECT_MEMBER_OR_ADMIN`: <https://opendev.org/openstack/nova/src/branch/master/nova/policies/console_output.py>
