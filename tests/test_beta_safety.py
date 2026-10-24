"""Static release-safety gates; these tests never execute device commands."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / "overlay/target/linux/sanechips/base-files"
boot = (base / "sbin/e2631-wifi-boot").read_text()
ap = (base / "sbin/e2631-wifi-ap").read_text()
fstab = (base / "etc/config/fstab").read_text()
init = (base / "sbin/e2631-userdata-init").read_text()

assert "leaving AP disabled until secured setup" in boot
assert '/sbin/e2631-wifi-ap OpenWrt' not in boot
assert 'e2631-wifi-ap off' in boot
assert 'refusing to create an open AP' in ap
assert 'exit 2' in ap
assert 'E2631_CONFIRM=ERASE_MTD10_USERDATA_47M' in init or 'ERASE_MTD10_USERDATA_47M' in init

# Keep this warning visible until an activation gate and upgrade compatibility
# have been implemented and tested on actual hardware.
assert "option enabled '1'" in fstab
print("PASS: beta wireless fail-closed defaults; unsafe extroot remains an explicit release blocker")
