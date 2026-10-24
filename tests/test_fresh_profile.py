"""Static guard for separating fresh-only images from legacy extroot upgrades."""
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
bootstrap = (repo / "scripts/bootstrap.sh").read_text()
build = (repo / "scripts/build.sh").read_text()
workflow = (repo / ".github/workflows/beta-build.yml").read_text()
rom_fstab = (repo / "overlay/target/linux/sanechips/base-files/etc/config/fstab").read_text()

assert "E2631_FRESH_INSTALL_ONLY" in bootstrap
assert "E2631_FRESH_INSTALL_ONLY" in build
assert "E2631_FRESH_INSTALL_ONLY: '1'" in workflow
assert 'option enabled \'1\'' in rom_fstab
assert 'option enabled \'0\'' in bootstrap
assert 'option enabled \'0\'' in build
assert "fresh-only build refused" in build
assert "automatic UBIFS Extroot disabled" in bootstrap

print("PASS: CI candidate build is fresh-only; legacy source profile unchanged")
