# E2631 Beta hardware acceptance plan

**Not permission to flash.** This is the test plan to use only after an
unverified candidate is built and independently inspected. Never start
with an irreplaceable/production router. Preserve a known-good recovery
route through the untouched vendor slot and UART.

## 0. Preflight / identification (read-only)

Record the board label/revision, currently installed software and
factory package version. From the running OpenWrt system, capture:

```sh
ubus call system board
cat /proc/mtd
cat /sys/class/mtd/mtd10/name
cat /sys/class/mtd/mtd10/size
cat /sys/class/ubi/ubi0/mtd_num 2>/dev/null
cat /sys/class/ubi/ubi0_0/name 2>/dev/null
dmesg | grep -Ei 'spi-nand|ubi|ubifs|mt791|pcie|l2c'
```

Do **not** assume `/dev/mtd10` identifies userdata on another firmware
or board revision: the dynamic rootfs_data split changes MTD numbering.
Redact passwords, public addresses, MACs/serials and credentials before
sharing logs. Do not post raw NAND dumps.

## 1. Fresh-install acceptance (fresh-only build profile)

- Confirm the candidate was built with
  `E2631_FRESH_INSTALL_ONLY=1` and ROM `fstab enabled '0'`.
- Independently verify image format, kernel/rootfs layout, slot bounds,
  image hash and factory header's compatibility with this board.
- Starting from a vendor system with **verified rollback**, use only
  the already documented and previously tested vendor web upgrade
  route. Do not issue manual NAND erase/write commands.
- Verify wired DHCP, SSH and LuCI before attempting Wi-Fi. Confirm
  there is no open default AP and no unprotected remote management.
- Confirm a blank userdata partition is not formatted or activated
  automatically; verify the internal JFFS2 overlay is functional.

**Stop** if the candidate loses wired manageability, changes the
vendor slot unexpectedly, or violates any NAND geometry checks.

## 2. Wi-Fi regression matrix

Run at least ten full power-removal cold starts on each supported board
variant; test 2.4 GHz and 5 GHz separately with WPA2 credentials,
client association, reconnect, DHCP, and 30 minutes of sustained
traffic. Keep UART recording through startup and association. Record
all hangs including silent UART/ARP loss; do not mark the historical
WIFI-COLD-BIND-HANG or WIFI-ASSOC-HARD-HANG resolved without evidence.

## 3. Migration/upgrade matrix — separate sacrificial test device

Do not use the fresh-install-only candidate for existing UBIFS
sysupgrade. Once the transactional copier and activation gate exist,
test all of the following on a separately backed-up board:

1. Existing legacy UBIFS without a new ready marker: preserve config.
2. New raw/erased userdata: remain on internal JFFS2 without writes.
3. Existing UBI with no upper/work: remain on JFFS2.
4. Interrupted copy with `.e2631-txn`: refuse activation.
5. Partial `upper` or dirty `work`: refuse activation.
6. Wrong mtd geometry, UBI0 mapping, volume name: refuse activation.
7. Verified migration with chr(0,0) whiteouts and
   `trusted.overlay.*` xattrs: independently verify retained metadata.
8. Unexpected power loss at every transaction boundary: no config loss
   and a recoverable previous state.

Only after these tests may a runtime gate be enabled.

## 4. Release evidence

For every device, record:

| Field | Value |
| --- | --- |
| Hardware revision / NAND manufacturer ID | _pending_ |
| Git commit / base / feeds SHAs | _pending_ |
| Candidate SHA256 | _pending_ |
| Factory firmware / active slot | _pending_ |
| Fresh vs legacy install path | _pending_ |
| Cold boots completed / failed | _pending_ |
| WPA2 associations (both bands) | _pending_ |
| Upgrade, preservation and rollback | _pending_ |
| UART logs / issue links (redacted) | _pending_ |

Passing build CI is necessary but never sufficient. A public prerelease
requires explicit supported revisions, checksums, evidence, warning
labels and a tested recovery guide. Stable requires additional
independent long-duration and multi-unit regression testing.
