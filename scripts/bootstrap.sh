#!/bin/bash
# Get a clean Linux box to the point where `make world` can succeed: base tree at
# the pinned commit, the E2631 overlay applied, the two feeds that matter
# installed, and the seed .config in place.
#
#   bash scripts/bootstrap.sh          # or: make bootstrap
#
# Idempotent: every step checks before it acts, so re-running after a failed
# build costs seconds. It never deletes a tree - if something looks wrong it
# stops and says what.
set -eu
cd "$(dirname "$0")/.."
. scripts/env.sh

say() { printf 'bootstrap: %s\n' "$*"; }
die() { printf 'bootstrap: %s\n' "$*" >&2; exit 1; }

e2631_need_cmd git "clone the base tree and the feeds" || exit 1
e2631_need_cmd make "drive the OpenWrt build" || exit 1
e2631_need_cmd gcc "build the toolchain (build-essential)" || exit 1
e2631_need_cmd g++ "build some host tools (build-essential)" || exit 1
e2631_need_cmd file "identify the built payloads" || exit 1

# ---- 1. the base tree --------------------------------------------------------
# A full clone, not a shallow one: the port is pinned to a commit that may not be
# the branch head, and a shallow clone cannot check out an arbitrary SHA.
if [ ! -d "$E2631_TREE" ]; then
	say "cloning $E2631_BASE_REPO#$E2631_BASE_SHA into $E2631_TREE"
	git clone --branch "$E2631_BASE_BRANCH" "$E2631_BASE_REPO" "$E2631_TREE" ||
		die "clone failed - network, or the branch moved? $E2631_BASE_REPO can be overridden in .env"
fi
[ -d "$E2631_TREE/target/linux/sanechips" ] ||
	die "no sanechips target in $E2631_TREE - that is not the base tree this kit overlays (set E2631_TREE, or remove the directory and re-run)"

if ! git -C "$E2631_TREE" rev-parse --verify "$E2631_BASE_SHA^{commit}" >/dev/null 2>&1; then
	say "fetching $E2631_BASE_BRANCH (the pinned commit is not in this clone yet)"
	git -C "$E2631_TREE" fetch origin "$E2631_BASE_BRANCH" ||
		die "cannot fetch $E2631_BASE_SHA - it must be reachable from $E2631_BASE_BRANCH"
fi
if [ "$(git -C "$E2631_TREE" rev-parse HEAD)" != "$E2631_BASE_SHA" ]; then
	if [ -n "$(git -C "$E2631_TREE" status --porcelain)" ]; then
		die "$E2631_TREE is at $(git -C "$E2631_TREE" rev-parse --short HEAD), not the pinned $E2631_BASE_SHA, and has uncommitted changes.
       Look at 'git -C $E2631_TREE status' first: if those edits are yours, point E2631_TREE at a
       fresh clone instead of overwriting them. If they are only a stale copy of this overlay,
       reset the tree to the pinned commit and re-run."
	fi
	say "checking out the pinned commit $E2631_BASE_SHA"
	git -C "$E2631_TREE" checkout -q "$E2631_BASE_SHA"
fi

# ---- 2. the overlay ----------------------------------------------------------
say "applying the E2631 overlay to $E2631_TREE"
bash "$E2631_KIT/apply.sh" "$E2631_TREE"

# Public Beta's initial-install profile must never auto-activate a possibly
# empty or partially migrated userdata. The historical source overlay is
# unchanged for existing UBIFS installations; cross-profile sysupgrade is
# deliberately NOT supported until hardware migration testing.
if [ "${E2631_FRESH_INSTALL_ONLY:-0}" = 1 ]; then
    FSTAB="$E2631_TREE/target/linux/sanechips/base-files/etc/config/fstab"
    [ -f "$FSTAB" ] || die "fresh-only: missing target fstab"
    grep -Eq "^[[:space:]]*option enabled '1'[[:space:]]*$" "$FSTAB" ||
        die "fresh-only: cannot locate original enabled Extroot entry"
    sed -i "s/option enabled '1'/option enabled '0'/" "$FSTAB"
    grep -Eq "^[[:space:]]*option enabled '0'[[:space:]]*$" "$FSTAB" ||
        die "fresh-only: failed to disable Extroot"
    say "FRESH-INSTALL-ONLY: automatic UBIFS Extroot disabled in build tree"
fi

# The two edits apply.sh must leave behind, checked here rather than trusted:
# both are what make the image boot on this board instead of the H3600.
grep -qx 'CONFIG_CMDLINE_FORCE=y' "$E2631_TREE/target/linux/sanechips/config-6.18" ||
	die "apply.sh left no forced kernel command line in $E2631_TREE - the vendor bootargs would win"
grep -q 'Makefile.e2631' "$E2631_TREE/target/linux/sanechips/image/Makefile" ||
	die "apply.sh did not hook image/Makefile - the E2631 device definition would be invisible"

# ---- 3. feeds ---------------------------------------------------------------
# Only packages and luci. Two traps, both hit in practice: a hand-cloned feed has
# no feeds/<name>.index and `feeds install` then says "Ignoring feed 'luci'" -
# the build still succeeds, just without LuCI, silently; and a killed half-clone
# leaves a shallow repo whose next pull re-fetches the full history.
for f in packages luci; do
	[ -d "$E2631_TREE/feeds/$f/.git" ] || {
		say "cloning feed $f"
		git clone -q --depth 1 --single-branch "https://github.com/openwrt/$f" "$E2631_TREE/feeds/$f"
	}
	# Optional immutable feed commits for CI / release reproducibility.
	# Never discard a maintainer's patched or otherwise dirty feed checkout.
	case "$f" in
	    packages) pinned=${E2631_PACKAGES_SHA:-} ;;
	    luci) pinned=${E2631_LUCI_SHA:-} ;;
	esac
	if [ -n "$pinned" ] && [ "$(git -C "$E2631_TREE/feeds/$f" rev-parse HEAD)" != "$pinned" ]; then
	    [ -z "$(git -C "$E2631_TREE/feeds/$f" status --porcelain)" ] ||
		die "feed $f has local edits; refusing to change its commit"
	    say "pinning feed $f at $pinned"
	    git -C "$E2631_TREE/feeds/$f" fetch -q --depth 1 origin "$pinned" ||
		die "cannot fetch pinned $f commit $pinned"
	    git -C "$E2631_TREE/feeds/$f" checkout -q --detach "$pinned"
	fi
	if [ -n "$pinned" ]; then
	    # 'feeds update' without -i would pull latest and undo the checkout.
	    say "indexing pinned feed $f without network update"
	    ( cd "$E2631_TREE" && ./scripts/feeds update -i "$f" 2>&1 | tail -3 )
	else
	    [ -f "$E2631_TREE/feeds/$f.index" ] || {
		    say "indexing feed $f"
		    ( cd "$E2631_TREE" && ./scripts/feeds update "$f" 2>&1 | tail -3 )
	    }
	fi
done
say "installing feed packages"
( cd "$E2631_TREE" && ./scripts/feeds install -a 2>&1 | grep -E "Ignoring|Installing" | tail -8 )
[ -d "$E2631_TREE/package/feeds/packages" ] || die "feed install produced no package/feeds/packages"

# ---- Python 3.14 target libffi dependency -----------------------------------
# This pinned base deliberately omits package/libs/libffi, while the pinned
# packages feed builds Python with --with-system-ffi. Python's _ctypes source
# unconditionally includes ffi.h during its target build: without a target
# libffi build dependency, a clean parallel CI run fails after ~50 minutes.
# Vendor the upstream libffi package in overlay/ and stage it before Python.
[ -f "$E2631_TREE/package/libs/libffi/Makefile" ] ||
    die "missing vendored target libffi package; check overlay/package/libs/libffi"
PYFFIPATCH="$E2631_KIT/patches/python3-libffi-build-dep.patch"
[ -f "$PYFFIPATCH" ] || die "missing Python target libffi build-dependency patch"
if git -C "$E2631_TREE/feeds/packages" apply --reverse --check "$PYFFIPATCH" 2>/dev/null; then
    say "Python libffi dependency patch already applied"
elif git -C "$E2631_TREE/feeds/packages" apply --check "$PYFFIPATCH" 2>/dev/null; then
    git -C "$E2631_TREE/feeds/packages" apply "$PYFFIPATCH" ||
        die "cannot apply Python libffi dependency patch"
    say "Python target build now depends on staged libffi headers"
else
    die "Python feed differs from pinned revision; refuse to guess at libffi build ordering"
fi
grep -Eq '^PKG_BUILD_DEPENDS:=libffi ' "$E2631_TREE/feeds/packages/lang/python/python3/Makefile" ||
    die "Python libffi dependency missing after patch"

# ---- E2631 LuCI attribution -----------------------------------------------
# Apply after cloning/installing feeds, before compiling LuCI.
LUCIPATCH="$E2631_KIT/patches/luci-bootstrap-footer.patch"

if git -C "$E2631_TREE/feeds/luci" apply --reverse --check "$LUCIPATCH" 2>/dev/null; then
        say "LuCI footer attribution already applied"
elif git -C "$E2631_TREE/feeds/luci" apply --check "$LUCIPATCH"; then
        git -C "$E2631_TREE/feeds/luci" apply "$LUCIPATCH"
        say "LuCI footer attribution applied: tigaotg"
else
        die "LuCI footer patch cannot be applied; check upstream template"
fi

# ---- 4. the seed config ----------------------------------------------------
say "seeding .config from seed/e2631.config"
cp "$E2631_KIT/seed/e2631.config" "$E2631_TREE/.config"
( cd "$E2631_TREE" && make defconfig >/dev/null 2>&1 )
for want in CONFIG_TARGET_DEVICE_sanechips_generic_DEVICE_zte_zxhn-e2631= \
	CONFIG_SOFT_FLOAT= CONFIG_PACKAGE_luci= CONFIG_PACKAGE_e2631-fwslot= \
	CONFIG_PACKAGE_rsync= CONFIG_RSYNC_xattr= CONFIG_RSYNC_acl=; do
	grep -q "^$want" "$E2631_TREE/.config" || die "seed check: $want missing after defconfig"
done
say "seed ok: E2631 device selected, soft-float on, LuCI and the slot tool in the image"

say "done. next: bash scripts/build.sh   (about 40 minutes on 2 cores, then it packs)"
