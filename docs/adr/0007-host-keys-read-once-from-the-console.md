# The orb's SSH host keys are read once from the console and stored

When an orb's machine has booted, the service reads its SSH host keys from the Nova console and stores them in the `orbs` table; the API returns them as `ssh_host_keys` so that the client connects with strict host key checking. The keys belong to the machine, so storing them is an exception to [stored state](../design/state.md)'s "we store only what we own". The reason is that the console is not a reliable owner. Nova returns only a bounded tail, so the boot block can scroll out on a chatty orb. A root process inside the orb can also print a forged block later. The image and its boot output are trusted inputs. orbit accepts a boot key block only within `ready_timeout` of the creation request and preserves the first collected keys; output produced later may come from a process inside the orb.

The block is the one both cloud-init (`keys_to_console`) and CirrOS (`cirros-status`) print. orbit treats the image's boot key block as its readiness signal, rather than probing the client's SSH path; [reconciliation](../design/state.md#reconciliation) defines the status observations. The console is read with `POST /servers/{id}/action` (`os-getConsoleOutput`), which changes nothing in Nova, under the project member's default policy and the requester's token ([0002](0002-resources-in-the-users-project.md)).

## Rejected alternatives

**Reading the console on every read, storing nothing.** The table would keep only what it owns, but boot keys could scroll out of the console buffer or be replaced by guest-generated output.

**A Heat WaitCondition**, signalled by cloud-init with the keys and exposed as a stack output. Heat would own the data and the stack would complete only once sshd is ready. Rejected because the machine would have to reach Heat's API from its own network ([0006](0006-own-network-per-orb.md)), the signal would travel over the network, and the WaitCondition's token would sit in the orb's metadata, readable by the agent inside.

## Accepted consequences

- An image that prints no block never becomes `ACTIVE`: its orbs end in `ERROR` after `ready_timeout`.
- The collection deadline is a trust boundary, not just a polling preference. Timeout coordination and restart behavior belong to [reconciliation](../design/state.md#reconciliation).

## Sources

- cloud-init's `write-ssh-key-fingerprints`, called by `cc_keys_to_console`: <https://github.com/canonical/cloud-init/blob/main/tools/write-ssh-key-fingerprints>
- CirrOS's `cirros-status`: <https://github.com/cirros-dev/cirros/blob/main/src/sbin/cirros-status>
- Nova's console limit, `MAX_CONSOLE_BYTES = 100 * units.Ki`: <https://opendev.org/openstack/nova/src/branch/master/nova/virt/libvirt/driver.py>
- Nova's console policy, `os_compute_api:os-console-output` with `PROJECT_MEMBER_OR_ADMIN`: <https://opendev.org/openstack/nova/src/branch/master/nova/policies/console_output.py>
