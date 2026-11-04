#!/bin/bash
# Build the Alpine aarch64 UEFI image that dev --orb boots (initializer:
# tiny-cloud, which applies orbit's cloud-config user data).
#   sudo build.sh
# Needs, in $B (lib.sh): dl/ with the frozen rootfs and APKs; run it from a copy
# of this directory on the DevStack VM, then upload.sh.
# Output: $B/out/alpine-<ver>-arm64-tinycloud-dev251.qcow2 (+ evidence under $B/out/evidence-tinycloud/)
set -euo pipefail
. "$(dirname "$0")/lib.sh"

V=tinycloud
[ "$(id -u)" = 0 ] || die "run as root"

W=$B/work/$V
R=$W/root
IMG=$W/$V.raw
OUT=$B/out/alpine-3.24-arm64-$V-dev251.qcow2
EVID=$B/out/evidence-$V
trap cleanup EXIT

mkdir -p "$W" "$R" "$EVID"
[ -z "$(mounts_below)" ] || die "stale mounts below $R"
detach_stale "$IMG"
rm -f "$IMG" "$OUT"

log "verify rootfs tarball"
echo "$ROOTFS_SHA256  $ROOTFS_TGZ" | sha256sum -c -

log "partition $IMG ($DISK_SIZE)"
truncate -s $DISK_SIZE "$IMG"
sgdisk -Z -o "$IMG" >/dev/null
sgdisk -n 1:0:+64M -t 1:EF00 -c 1:ESP -n 2:0:0 -t 2:8305 -c 2:rootfs "$IMG" >/dev/null
LOOP=$(losetup --find --show -P "$IMG")
for i in $(seq 1 20); do [ -b "${LOOP}p1" ] && [ -b "${LOOP}p2" ] && break; partprobe "$LOOP" 2>/dev/null || true; sleep 0.5; done
[ -b "${LOOP}p1" ] && [ -b "${LOOP}p2" ] || die "partition nodes missing for $LOOP"
mkfs.vfat -F 32 -n ESP "${LOOP}p1" >/dev/null
mkfs.ext4 -q -L rootfs -O ^orphan_file -E nodiscard "${LOOP}p2"
ROOT_UUID=$(blkid -s UUID -o value "${LOOP}p2")
ESP_UUID=$(blkid -s UUID -o value "${LOOP}p1")
log "root uuid $ROOT_UUID esp uuid $ESP_UUID"

mount "${LOOP}p2" "$R"
mkdir -p "$R/boot/efi"
mount "${LOOP}p1" "$R/boot/efi"
tar -xzpf "$ROOTFS_TGZ" --numeric-owner -C "$R"
bind_pseudo
cp /etc/resolv.conf "$R/etc/resolv.conf"

log "apk repositories and base packages"
cat > "$R/etc/apk/repositories" <<EOF
https://dl-cdn.alpinelinux.org/alpine/v3.24/main
https://dl-cdn.alpinelinux.org/alpine/v3.24/community
EOF
mkdir -p "$R/etc/mkinitfs"
cat > "$R/etc/mkinitfs/mkinitfs.conf" <<EOF
features="base ext4 virtio"
EOF
# Retained exact-version inputs, including all transitive dependencies. No
# repository resolution or downloads; apk still verifies Alpine signatures.
ARCHIVE=$B/dl/packages/$V
(cd "$ARCHIVE" && sha256sum -c SHA256SUMS)
mkdir -p "$R/tmp/packages"
while read -r hash file; do
	cp "$ARCHIVE/$file" "$R/tmp/packages/"
done < "$ARCHIVE/SHA256SUMS"
in_chroot sh -c 'apk add --no-network --no-cache /tmp/packages/*.apk'
rm -rf "$R/tmp/packages"

log "kernel / initramfs"
KVER=$(ls "$R/lib/modules" | head -n1)
[ "$(ls "$R/lib/modules" | wc -l)" = 1 ] || die "expected exactly one kernel in /lib/modules"
in_chroot mkinitfs -o /boot/initramfs-virt "$KVER"
ls -l "$R/boot"
printf '%s\n' "$KVER" > "$EVID/kernel-version"

log "users, sudo, ssh, console, fstab"
in_chroot sh -c '
	addgroup -S wheel 2>/dev/null || true
	addgroup ubuntu
	adduser -D -h /home/ubuntu -s /bin/bash -G ubuntu ubuntu
	addgroup ubuntu wheel
	echo "ubuntu:*" | chpasswd -e
	passwd -l root >/dev/null
'
echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > "$R/etc/sudoers.d/ubuntu"
chmod 0440 "$R/etc/sudoers.d/ubuntu"
mkdir -p "$R/etc/ssh/sshd_config.d"
if ! grep -q '^Include /etc/ssh/sshd_config.d' "$R/etc/ssh/sshd_config"; then
	sed -i '1i Include /etc/ssh/sshd_config.d/*.conf' "$R/etc/ssh/sshd_config"
fi
cat > "$R/etc/ssh/sshd_config.d/10-dev.conf" <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers ubuntu
EOF
echo alpine > "$R/etc/hostname"
cat > "$R/etc/fstab" <<EOF
UUID=$ROOT_UUID / ext4 rw,relatime 0 1
EOF
cat > "$R/etc/inittab" <<'EOF'
::sysinit:/sbin/openrc sysinit
::sysinit:/sbin/openrc boot
::wait:/sbin/openrc default
ttyAMA0::respawn:/sbin/getty -L 115200 ttyAMA0 vt100
::ctrlaltdel:/sbin/reboot
::shutdown:/sbin/openrc shutdown
EOF
# GNU grep/find (find -printf) must win over busybox applets on any PATH order.
for t in grep find xargs; do
	gnu=
	for d in /usr/bin /bin; do
		if [ -x "$R$d/$t" ] && [ "$(readlink "$R$d/$t" || true)" != /bin/busybox ] && [ "$(readlink "$R$d/$t" || true)" != busybox ]; then gnu=$d/$t; break; fi
	done
	[ -n "$gnu" ] || die "no GNU $t installed"
	for d in /usr/bin /bin; do
		[ "$d/$t" = "$gnu" ] || { [ ! -L "$R$d/$t" ] || ln -sf "$gnu" "$R$d/$t"; }
	done
	log "GNU $t at $gnu"
done

log "services"
rcadd() { in_chroot rc-update add "$1" "$2" >/dev/null; }
for s in devfs dmesg mdev hwdrivers; do rcadd $s sysinit; done
for s in modules sysctl hostname bootmisc networking syslog hwclock urandom seedrng; do
	[ -e "$R/etc/init.d/$s" ] && rcadd $s boot || log "note: no init script $s"
done
for s in mount-ro killprocs savecache; do [ -e "$R/etc/init.d/$s" ] && rcadd $s shutdown; done
rcadd sshd default

rcadd tiny-cloud-boot boot
for s in early main final; do rcadd tiny-cloud-$s default; done
# post-install of tiny-cloud-openstack wrote CLOUD=openstack; pin the rest.
cat >> "$R/etc/tiny-cloud.conf" <<EOF

# dev #251: ConfigDrive only, user ubuntu. User data is saved and organized
# (orbit's cloud-config write_files for the egress proxy); scripts stay skipped.
CLOUD=openstack
IMDS_SOURCE=configdrive
IMDS_FORMAT=native
CLOUD_USER=ubuntu
CLOUD_USER_SHELL=/bin/bash
SKIP_INIT_ACTIONS="run_userdata"
EOF
install -d -m 0755 "$R/usr/local/sbin"
install -m 0755 "$(dirname "$0")/files/dev-host-key-console" "$R/usr/local/sbin/dev-host-key-console"
install -m 0755 "$(dirname "$0")/files/dev-host-key-console.initd" "$R/etc/init.d/dev-host-key-console"
rcadd dev-host-key-console default

log "boot loader"
CMDLINE="root=UUID=$ROOT_UUID rootfstype=ext4 rootwait modules=ext4 console=tty0 console=ttyAMA0,115200n8 net.ifnames=0"
mkdir -p "$R/boot/grub" "$R/boot/efi/EFI/BOOT"
cat > "$R/boot/grub/grub.cfg" <<EOF
set timeout=0
set default=0
menuentry "Alpine Linux $KVER" {
	linux /boot/Image-virt $CMDLINE
	initrd /boot/initramfs-virt
}
EOF
cat > "$R/tmp/embed.cfg" <<EOF
search --no-floppy --fs-uuid --set=root $ROOT_UUID
set prefix=(\$root)/boot/grub
configfile (\$root)/boot/grub/grub.cfg
EOF
in_chroot grub-mkimage -O arm64-efi -o /boot/efi/EFI/BOOT/BOOTAA64.EFI -c /tmp/embed.cfg -p /boot/grub \
	part_gpt part_msdos fat ext2 search search_fs_uuid normal configfile linux echo test serial terminal gzio all_video
rm -f "$R/tmp/embed.cfg"
# Alpine's aarch64 vmlinuz is an EFI zboot image (MZ + "zimg" + gzip payload);
# GRUB's arm64 loader needs a plain Image, so unpack the payload at build time.
od -A d -t x1z -N 64 "$R/boot/vmlinuz-virt" > "$EVID/vmlinuz-header.txt"
[ "$(dd if="$R/boot/vmlinuz-virt" bs=1 skip=4 count=4 2>/dev/null)" = zimg ] || die "vmlinuz is not zboot"
[ "$(dd if="$R/boot/vmlinuz-virt" bs=1 skip=24 count=4 2>/dev/null)" = gzip ] || die "zboot payload is not gzip"
ZOFF=$(od -An -t u4 -j8 -N4 "$R/boot/vmlinuz-virt" | tr -d ' ')
ZLEN=$(od -An -t u4 -j12 -N4 "$R/boot/vmlinuz-virt" | tr -d ' ')
dd if="$R/boot/vmlinuz-virt" bs=1M iflag=skip_bytes,count_bytes skip="$ZOFF" count="$ZLEN" 2>/dev/null | gzip -dc > "$R/boot/Image-virt"
[ "$(dd if="$R/boot/Image-virt" bs=1 skip=56 count=4 2>/dev/null)" = "ARM$(printf '\144')" ] || die "unpacked kernel lacks arm64 Image magic"
chmod 0644 "$R/boot/Image-virt"
ls -l "$R/boot/Image-virt"

log "package manifest"
in_chroot apk info -vv | sort > "$EVID/packages.txt"
in_chroot apk list -I | sort > "$EVID/packages-installed.txt"

log "sanitize"
rm -f "$R"/etc/ssh/ssh_host_* "$R/etc/machine-id" "$R/var/lib/dbus/machine-id"
rm -rf "$R/root/.ssh" "$R/home/ubuntu/.ssh" "$R/root/.ash_history" "$R/root/.bash_history" "$R/home/ubuntu/.bash_history"
rm -rf "$R/var/lib/cloud" "$R/var/log/cloud-init"* "$R/run/tiny-cloud" "$R/var/log/tiny-cloud"* "$R/etc/cloud/ssh_host" 2>/dev/null || true
find "$R/var/cache/apk" -mindepth 1 -delete 2>/dev/null || true
find "$R/tmp" -mindepth 1 -delete 2>/dev/null || true
find "$R/var/log" -type f -exec truncate -s 0 {} + 2>/dev/null || true
find "$R/var/tmp" -mindepth 1 -delete 2>/dev/null || true
: > "$R/etc/resolv.conf"
# hostkey/clientkey scan (evidence)
{
	echo "# private-key material or authorized_keys found (must be empty):"
	grep -rIl -e 'BEGIN [A-Z ]*PRIVATE KEY' "$R/etc" "$R/root" "$R/home" "$R/var" "$R/usr/local" "$R/boot" 2>/dev/null || true
	find "$R/etc" "$R/root" "$R/home" "$R/var" \( -name 'authorized_keys*' -o -name 'ssh_host_*' -o -name 'id_*' -o -name '.bash_history' \) 2>/dev/null || true
	ls "$R/etc/machine-id" "$R/var/lib/dbus/machine-id" 2>/dev/null || true
} > "$EVID/sanitize-scan.txt"
cat "$EVID/sanitize-scan.txt"
sync

log "fstrim, unmount, fsck"
fstrim "$R" || true
fstrim "$R/boot/efi" || true
umount_all
e2fsck -fn "${LOOP}p2" | tee "$EVID/e2fsck.txt" | tail -2
losetup -d "$LOOP"; LOOP=

log "qcow2"
qemu-img convert -c -O qcow2 "$IMG" "$OUT"
qemu-img check "$OUT"
qemu-img info "$OUT" | tee "$EVID/qemu-img-info.txt"
sha256sum "$OUT" | tee "$EVID/sha256"
sha512sum "$OUT" | tee "$EVID/sha512"
chmod 0644 "$OUT"
log "done: $OUT"
