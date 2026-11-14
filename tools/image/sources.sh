#!/bin/sh
# Collect the source of every package in the orb image: the aports directory
# each package was built from, at the commit its apk database records, and the
# archives its APKBUILD names, checked against the APKBUILD's sha512sums.
#   sources.sh <apk-installed-db> <output.tar>
# Runs as root on Alpine with abuild, git and GNU tar (README: Licenses and
# sources). The database is /lib/apk/db/installed of the image.
set -eu
. "$(dirname "$0")/lib.sh"

[ $# = 2 ] || { echo "usage: $0 <apk-installed-db> <output.tar>" >&2; exit 2; }
DB=$(realpath "$1")
OUT=$(realpath "$2")
NAME=$(basename "$OUT" .tar)
APORTS=https://gitlab.alpinelinux.org/alpine/aports.git
DISTFILES_MIRROR=https://distfiles.alpinelinux.org/distfiles/v${ALPINE_VER%.*}
export DISTFILES_MIRROR CARCH=aarch64

W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
git init -q --bare "$W/aports.git"
git -C "$W/aports.git" remote add origin "$APORTS"
mkdir "$W/$NAME"

# One "<origin> <version> <commit>" line per source package.
awk -F: '
	function flush() {
		if (p == "") return
		if (o == "" || c == "") { print p ": no origin or aports commit" > "/dev/stderr"; exit 1 }
		print o, v, c; p = o = v = c = ""
	}
	/^P:/ { p = $2 } /^o:/ { o = $2 } /^V:/ { v = $2 } /^c:/ { c = $2 }
	/^$/ { flush() } END { flush() }
' "$DB" > "$W/packages"
sort -u "$W/packages" > "$W/origins"
dup=$(cut -d' ' -f1 "$W/origins" | uniq -d)
[ -z "$dup" ] || { echo "origin with several versions: $dup" >&2; exit 1; }

while read -r origin version commit; do
	git -C "$W/aports.git" fetch -q --depth 1 --filter=blob:none origin "$commit" < /dev/null
	repo=
	for r in main community testing; do
		if git -C "$W/aports.git" cat-file -e "$commit:$r/$origin/APKBUILD" 2>/dev/null; then
			repo=$r; break
		fi
	done
	[ -n "$repo" ] || { echo "$origin: no APKBUILD at $commit" >&2; exit 1; }

	dir=$W/$NAME/$origin-$version
	mkdir "$dir"
	git -C "$W/aports.git" archive "$commit" "$repo/$origin" | tar -x -C "$dir" --strip-components 2
	built=$(cd "$dir" && set +u && . ./APKBUILD && echo "$pkgver-r$pkgrel")
	[ "$built" = "$version" ] || { echo "$origin: APKBUILD at $commit is $built, not $version" >&2; exit 1; }
	(cd "$dir" && abuild -F -s "$dir" fetch verify < /dev/null > /dev/null)
	rm -rf "$dir/src"
	echo "$origin $version $repo $commit" >> "$W/$NAME/packages.txt"
	echo "$origin-$version"
done < "$W/origins"

tar -c -f "$OUT" -C "$W" --sort=name --owner=0 --group=0 --numeric-owner "$NAME"
