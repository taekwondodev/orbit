# Alpine image for orbit

Build an aarch64 UEFI image with tiny-cloud as its initializer. The image is intended to meet orbit's [image requirements](../../docs/architecture.md#images-other-than-cirros). The build applies cloud-config files but skips user-data scripts; preserve that distinction when changing the initializer.

## Build machine and inputs

Use an aarch64 Linux machine with root access: the build mounts filesystems and runs `chroot` into an aarch64 root filesystem. On Debian or Ubuntu, install the build tools:

```console
$ sudo apt install gdisk qemu-utils dosfstools parted e2fsprogs
```

The build also uses `mount`, `util-linux` and `coreutils`. [lib.sh](lib.sh) defines the scratch directory (`B`), root filesystem archive and expected checksum. [build.sh](build.sh) defines the output paths and package archive layout.

The input archive is not supplied by this repository. Obtain the complete inputs before starting:

- The root filesystem tarball at `ROOTFS_TGZ`, matching `ROOTFS_SHA256` in `lib.sh`.
- `$B/dl/packages/tinycloud/`, containing all APKs and their transitive dependencies, with a `SHA256SUMS` manifest listing one `<sha256>  <file>` entry per APK.

The build verifies those checksums and installs the listed APKs without downloading or resolving packages; apk also checks package signatures. Retain the inputs and manifest together: upstream repositories may stop serving the exact versions. A checksum manifest alone is not a package archive.

## Build and upload

From the repository root:

```console
$ sudo tools/image/build.sh
```

The script replaces its previous work image and qcow2 output. Before upload, inspect the evidence directory named by `EVID` in `build.sh`: the filesystem and qcow2 checks must succeed, and the private-key and machine-identity scan must contain no findings. Builds are not bit-for-bit reproducible because timestamps and filesystem UUIDs vary.

On the DevStack host, upload to Glance:

```console
$ tools/image/upload.sh
```

[upload.sh](upload.sh) uses the local `stack` account and DevStack's `demo` project credentials. It defines the image name and Glance properties and refuses to replace an existing image with that name. Check for consumers before removing an old image. After upload, use the image's name or ID in an orb creation request and run the [image acceptance check](../../docs/architecture.md#images-other-than-cirros).

Keep the upload's `hw_scsi_model` property when changing the image: without the virtio SCSI driver/controller match, the config drive may be unreadable and the orb can boot without its key.
