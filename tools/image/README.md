# The orb image

Build the image every orb boots ([0010](../../docs/adr/0010-one-orb-image.md)): Alpine Linux, aarch64, UEFI, with tiny-cloud as its initializer. It meets orbit's [image requirements](../../docs/architecture.md#the-orb-image). The build applies cloud-config files but skips user-data scripts; preserve that distinction when changing the initializer.

Operators do not build it: the [DevStack plugin](../../devstack/plugin.sh) downloads the published release asset. Rebuild only to change the image.

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

## Build

From the repository root:

```console
$ sudo tools/image/build.sh
```

The script replaces its previous work image and qcow2 output. Inspect the evidence directory named by `EVID` in `build.sh`: the filesystem and qcow2 checks must succeed, and the private-key and machine-identity scan must contain no findings. Builds are not bit-for-bit reproducible because timestamps and filesystem UUIDs vary.

## Publish

1. Run the [acceptance check](../../docs/architecture.md#the-orb-image) on a DevStack with the new image uploaded under the name in `[orbs] image`.
2. Build the [source archive](#licenses-and-sources), then publish the qcow2 under a new release tag, with the package list from the evidence directory, the source archive and the source notice below:

   ```console
   $ gh release create <tag> <qcow2> <evidence>/packages-installed.txt <sources.tar> \
         --repo taekwondodev/orbit --title "Orb image <tag>" --notes-file <notes>
   ```

3. Update `ORBIT_IMAGE_URL` and `ORBIT_IMAGE_SHA256` in [plugin.sh](../../devstack/plugin.sh) in the same commit. When the image's contents change, also change its Glance name (`ORBIT_IMAGE_NAME` in [settings](../../devstack/settings) and the `[orbs] image` default in [orbit/conf.py](../../orbit/conf.py)), because the plugin does not replace an image that already has its name.

Never replace the asset of an existing release: deployments pin its checksum.

## Licenses and sources

The image redistributes Alpine Linux packages, some under the GPL, so each release carries their source next to the qcow2. [sources.sh](sources.sh) builds that archive from the image's apk database (`apk-installed` in the evidence directory): for every package, the [aports](https://gitlab.alpinelinux.org/alpine/aports) directory at the commit the package was built from, and the archives its APKBUILD names, checked against its sha512sums. `packages.txt` in the archive lists each package's version, aports repository and commit. tiny-cloud comes from Alpine `edge`. Run it in an Alpine container of the image's release:

```console
$ docker run --rm -v "$PWD/tools/image:/tools:ro" -v "<evidence>:/in:ro" -v "$PWD/out:/out" alpine:3.24 \
      sh -c 'apk add -q abuild git tar && /tools/sources.sh /in/apk-installed /out/orbit-alpine-<ver>-sources.tar'
```

The release notes name the Alpine version and the source archive. Adding the source archive to an existing release is safe: deployments pin only the qcow2.
