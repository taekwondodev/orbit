# The orb's SSH host keys are read once from the console and stored

When an orb's machine has booted, the service reads its SSH host keys from the Nova console and stores them in the `orbs` table; the API returns them as `ssh_host_keys` so that the client connects with strict host key checking. The keys are the one thing the table keeps that someone else owns, an exception to [stored state](../design/state.md)'s "we store only what we own". The reason is that the console is not a reliable owner. Nova returns only its last part (100 KiB with libvirt), so the boot block scrolls out on a chatty orb. A root process inside the orb can also print a forged block later. Only the first block, printed at boot while only the image's code runs, is trusted, and it is read once. The console is read only within `ready_timeout` of the creation request: a block that appears later may come from inside the orb, so an orb past that limit without keys stays in `ERROR`.

The block is the one both cloud-init (`keys_to_console`) and CirrOS (`cirros-status`) print, between `-----BEGIN SSH HOST KEY KEYS-----` and `-----END SSH HOST KEY KEYS-----`. Its appearance is also the readiness signal: an orb is `ACTIVE` only once its keys are stored, and an image that prints no block ends in `ERROR` after `ready_timeout`. The console is read with `POST /servers/{id}/action` (`os-getConsoleOutput`), which changes nothing in Nova, under the project member's default policy and the requester's token ([0002](0002-resources-in-the-users-project.md)).

## Rejected alternatives

**Reading the console on every read, storing nothing.** The table would keep only what it owns, but the keys would disappear after 100 KiB of console and could be replaced from inside the orb.

**A Heat WaitCondition**, signalled by cloud-init with the keys and exposed as a stack output. Heat would own the data and the stack would complete only once sshd is ready. Rejected because the machine would have to reach Heat's API from its own network ([0006](0006-own-network-per-orb.md)), the signal would travel over the network, and the WaitCondition's token would sit in the orb's metadata, readable by the agent inside.

## Accepted consequences

- A column and a migration. The keys are written once, together with the transition to `ACTIVE`, and the console is not read again; the write applies only while no keys are stored.
- `ready_timeout` counts from the creation request, so it includes the wait for the reservation and the stack: orbit-api does not start unless it is greater than `creation_timeout`.

## Sources

- cloud-init's `write-ssh-key-fingerprints`, called by `cc_keys_to_console`: <https://github.com/canonical/cloud-init/blob/main/tools/write-ssh-key-fingerprints>
- CirrOS's `cirros-status`: <https://github.com/cirros-dev/cirros/blob/main/src/sbin/cirros-status>
- Nova's console limit, `MAX_CONSOLE_BYTES = 100 * units.Ki`: <https://opendev.org/openstack/nova/src/branch/master/nova/virt/libvirt/driver.py>
- Nova's console policy, `os_compute_api:os-console-output` with `PROJECT_MEMBER_OR_ADMIN`: <https://opendev.org/openstack/nova/src/branch/master/nova/policies/console_output.py>
