# Shared helpers for the dev #251 image builds. Sourced by build.sh and sources.sh; run as root.
# Everything is confined to $B (/var/tmp/dev-251-build).

B=/var/tmp/dev-251-build
ALPINE_VER=3.24.3
ROOTFS_TGZ=$B/dl/rootfs/alpine-minirootfs-$ALPINE_VER-aarch64.tar.gz
ROOTFS_SHA256=4d3f80afaebd447c5591a63a73bde380a149fe8b2d85488cafabb2ff97551f50
DISK_SIZE=2G
ROOT_UUID=
LOOP=
R=
W=

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# Mount points currently mounted at or below $R, deepest first.
mounts_below() {
	findmnt -rn -o TARGET | awk -v r="$R" 'index($0, r "/") == 1 || $0 == r' | sort -r
}

umount_all() {
	[ -n "$R" ] || return 0
	local i t
	for i in 1 2 3; do
		mounts_below | while read -r t; do umount "$t" || true; done
		[ -z "$(mounts_below)" ] && return 0
		sleep 1
	done
	[ -z "$(mounts_below)" ] || die "mounts remain below $R: $(mounts_below | tr '\n' ' ')"
}

cleanup() {
	set +e
	umount_all
	if [ -n "$LOOP" ] && losetup "$LOOP" >/dev/null 2>&1; then losetup -d "$LOOP"; fi
}

# Detach loop devices that point at our own image file only.
detach_stale() {
	local img="$1" d
	for d in $(losetup -j "$img" -O NAME -n 2>/dev/null); do losetup -d "$d"; done
}

in_chroot() { chroot "$R" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin TERM=dumb "$@"; }

bind_pseudo() {
	mkdir -p "$R/proc" "$R/sys" "$R/dev"
	mount -t proc proc "$R/proc"
	mount -t sysfs sysfs "$R/sys"
	mount --bind /dev "$R/dev"
	mount --make-private "$R/dev"
}
