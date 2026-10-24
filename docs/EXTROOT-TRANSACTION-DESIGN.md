# E2631 Extroot migration transaction design — proposal, not implemented

**Status:** design for `beta/public-readiness`, NOT an activation procedure.
No command in this document authorizes NAND formatting or enabling Extroot.

## Ground truth

- A known device already runs UBIFS at `/dev/ubi0_0` on mtd10, but
  a fresh userdata volume, migration and power-loss recovery have not
  been validated on real hardware.
- The source internal JFFS2 upperdir contains OverlayFS chr(0,0)
  whiteouts and may contain `trusted.overlay.*` extended attributes.
- The old `cp -a` staging program cannot prove metadata preservation
  and was disabled on this branch.
- Existing legacy UBIFS extroots may have `upper/work` without any
  `.e2631-extroot-ready` marker. Do not break or erase them.

See Linux [OverlayFS documentation](https://docs.kernel.org/filesystems/overlayfs.html)
for both whiteout representations (character 0:0 and xattr) and opaque
directory markers. A single `rename()` operation can atomically change
one name, but coordinating multiple names and durable persistence needs
careful ordering, syncing data and parent directories; see
[rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html) and
[fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html).

## Proposed states

| State | Evidence | Boot decision |
| --- | --- | --- |
| RAW | no validated UBI userdata | internal JFFS2, no write |
| EMPTY_UBI | expected volume, no completed overlay | internal JFFS2, no write |
| COPYING | `.e2631-txn` intent/staging directory exists | internal JFFS2; require human recovery |
| VERIFIED | copy plus exhaustive metadata comparison finished | still internal JFFS2 |
| COMMITTED | atomic ready marker plus correct layout, no txn | candidate only; hardware validation needed |
| LEGACY | `upper/work` without marker or txn | preserve, never auto-format; compatibility rules pending |
| INVALID | unexpected geometry, symlink, work contents or failed verification | internal JFFS2 and diagnostic |

Neither directory presence nor a hand-created text marker authenticates a
successful metadata-preserving copy. The final runtime gate must validate
device identity and a trustworthy migration provenance, and must not
treat `LEGACY` as automatically new/empty.

## Required implementation sequence

1. **Source quiescence:** run from a rescue/maintenance environment with
   internal JFFS2 upperdir no longer receiving writes. Confirm correct
   device identities and backup/recovery capability.
2. **Metadata-safe copier:** preserve file type and data, hard links,
   symbolic links, ownership, permissions, timestamps, all relevant
   extended attributes and character-device whiteouts. No partial success
   permitted. Build an independent destination comparison, including
   xattrs and device major/minor numbers.
3. **Stage without activation:** create `.e2631-txn` on UBIFS, put the
   prospective upperdir inside it, fsync files/directories and the
   transaction journal. A power failure here leaves old JFFS2 active.
4. **Commit:** prepare a fresh empty workdir and a durable completion
   record, then make the new layout visible with carefully ordered
   directory rename(s) and parent-directory fsync. The runtime gate
   must reject **every intermediate state**. Never claim that two
   independent renames are atomic as a group.
5. **First boot:** perform read-only checks before any activation,
   preserve unknown legacy installations, and only then permit switching
   overlay for an explicitly supported device state. Never initialize
   NAND automatically.
6. **Recovery:** test power loss after each write/rename/sync boundary,
   failed checksum/metadata comparison, storage-full conditions and
   repeated reboot. Do not remove the old JFFS2 source before successful
   long-running hardware validation.

## Exit criteria for enabling runtime activation

- Unit tests for every state and failure boundary; no mock writes to NAND.
- Two-way compare of content and metadata with a fixture containing
  chr(0,0) whiteouts and `trusted.overlay.opaque`/whiteout xattrs.
- Real UBIFS mount/replay + power-cut tests on a sacrificial board with
  UART and known-good vendor slot.
- Existing legacy extroot upgrade preserves settings with and without
  the new marker; fresh blank userdata never triggers auto-erase.
- Independent reviewer confirms that `fstab enabled 1` cannot bypass
  the policy, including dynamic `rootfs_data` MTD enumeration.

**Current code only identifies unsafe states. It does not implement this
transaction, enable runtime activation or solve legacy compatibility.**

## Independent host-side comparison (implemented, not integrated)

`python3 tools/compare_overlay_upper.py SOURCE_UPPER STAGED_UPPER`
recursively compares path sets, regular-file SHA256, type, owner/group,
permission bits, nanosecond mtime, symlink targets, device major/minor,
xattr names/bytes and hardlink relationships. It follows no symlinks
and fails closed if a source or destination attribute is unreadable.

It **does not copy any files** and requires sufficiently privileged
access to the raw JFFS2 and UBIFS upperdirs. Comparing only the merged
`/` view is invalid because OverlayFS hides whiteouts and opaque
metadata. A successful comparison does not prove crash consistency,
boot compatibility or complete copy fidelity on device; it is one
necessary acceptance check, not authority to write an activation marker.
