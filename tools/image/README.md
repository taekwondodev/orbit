# Image of `dev --orb`

Builds `alpine-3.24-arm64-tinycloud-dev251`: Alpine Linux 3.24.3, aarch64, UEFI, with tiny-cloud as initializer. tiny-cloud reads the config drive, writes orbit's cloud-config user data (the egress proxy settings) before sshd starts, and prints the host keys to the console. User-data scripts stay skipped (`SKIP_INIT_ACTIONS="run_userdata"`).

## Build machine

An aarch64 machine: the build runs `chroot` into an aarch64 root filesystem, so it does not run under x86. Start from Ubuntu Server 24.04.5 (noble):

```console
$ sudo apt install gdisk qemu-utils dosfstools parted e2fsprogs
```

`mount`, `util-linux` and `coreutils` come with the server image. Run the scripts as root. The scratch directory is `/var/tmp/dev-251-build` (`B` in `lib.sh`), and needs about 3 GB free.

## `dl/`: the build's inputs

The build downloads nothing. It reads `$B/dl/`, which is not in the repository, and stops if a checksum differs:

```text
/var/tmp/dev-251-build/dl/
├── rootfs/
│   └── alpine-minirootfs-3.24.3-aarch64.tar.gz
└── packages/
    └── tinycloud/
        ├── SHA256SUMS
        └── *.apk
```

- `rootfs/alpine-minirootfs-3.24.3-aarch64.tar.gz` is Alpine's minimal root filesystem. `ROOTFS_SHA256` in `lib.sh` pins its hash.
- `packages/tinycloud/` holds every package of the image, 95 APKs with all their transitive dependencies, and `SHA256SUMS`, one `<sha256>  <file>` line per APK. The build copies exactly those files into the root filesystem and installs them with `apk add --no-network`; apk still checks Alpine's signatures. No repository is resolved, so a newer package never changes the image.
- All the APKs come from Alpine's `v3.24` `main` and `community` repositories, except the three tiny-cloud ones (`tiny-cloud`, `tiny-cloud-openrc`, `tiny-cloud-openstack`, version `3.5.0_rc6-r0`), which come from `edge/main`. Edge removes old versions, so keep `dl/` once you have it: it is the only copy of those three files that this directory can rebuild from.

## Build and upload

```console
$ sudo tools/image/build.sh
```

Output: `out/alpine-3.24-arm64-tinycloud-dev251.qcow2`, and `out/evidence-tinycloud/` with the package list, the kernel version, the checksums and a scan for private keys. The builds are not bit-for-bit reproducible (timestamps, filesystem UUIDs).

On the DevStack host, `upload.sh` creates the Glance image in the `demo` project:

```console
$ tools/image/upload.sh
```

It refuses to run if an image with that name exists: delete the old one first. `dev --orb` selects the image by name, so a new image with the same name needs no change in dev's configuration. `stack.sh` deletes every Glance image: upload again after it.

Glance needs these properties on the image, `upload.sh` sets them: `hw_architecture=aarch64`, `hw_firmware_type=uefi`, `hw_machine_type=virt`, `hw_rng_model=virtio`, `hw_scsi_model=virtio-scsi` and `img_config_drive=mandatory`. Without `hw_scsi_model`, Nova attaches the config drive with a controller the image has no driver for, and the orb boots without its key.
