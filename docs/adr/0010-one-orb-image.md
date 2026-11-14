# Every orb boots the same image

Every orb boots the image that [tools/image](../../tools/image/README.md) builds. Neither the client nor the operator chooses a different one. Several orbit behaviors depend on what runs inside the machine: the config drive that installs the client's key, the host key block on the console that makes an orb `ACTIVE` ([0007](0007-host-keys-read-once-from-the-console.md)), the proxy settings applied before sshd starts ([0009](0009-default-deny-egress.md)), and the SSH user the API returns. With an arbitrary image, an orb could look healthy without those behaviors, and orbit would have no means to notice.

The image is published once as an asset of a GitHub release of this repository. The [DevStack plugin](../../devstack/plugin.sh) downloads it, checks its pinned SHA-256 and uploads it to Glance, so operators do not build it.

## Rejected alternatives

**An image chosen per request, with an operator default.** This was the previous contract. Each additional image had to meet the requirements above and needed its own SSH user mapping, and nothing enforced either.

**An operator-declared list of supported images.** This keeps the choice but bounds it. Rejected as more than the project needs: one image covers its use, and the list would keep the mapping and acceptance work that the single image removes.

## Accepted consequences

- The `POST /v1/orbs` body has no `image` field, and a client that still sends one has it ignored like any unknown field. Responses have no `image` field. `ssh_user` is always the user the image creates.
- The `orbs` table has no `image` column. orbit creates its schema at start without migrations, so an existing table keeps the column until it is dropped by hand or the database is recreated (DevStack recreates it on every `stack.sh`).
- The image is aarch64 only. Orbs need an aarch64 compute host.
- Other software in the orb means rebuilding the image, publishing it under a new release, and updating the plugin's URL and checksum together. The image's requirements are listed in [architecture](../architecture.md#the-orb-image).
- DevStack's CirrOS image is no longer used by orbit.
