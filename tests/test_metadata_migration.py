"""Source-only metadata hazard tests. No MTD or real overlay is modified."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
base = root / "overlay/target/linux/sanechips/base-files/sbin"
migrate = base / "e2631-userdata-migrate"
audit = base / "e2631-overlay-metadata-audit"

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    upper = path / "upper"
    upper.mkdir()
    tool = path / "tool"
    tool.mkdir()
    (tool / "find").symlink_to("/usr/bin/find")
    env = os.environ.copy()
    # Hermetic PATH makes the missing-getfattr case portable across runners.
    env["PATH"] = str(tool)

    def check(expected, code):
        p = subprocess.run(["sh", str(audit), "--inspect-upper", str(upper)], env=env, capture_output=True, text=True)
        assert (p.stdout.splitlines()[0], p.returncode) == (expected, code), p

    # Tool absent is unknown, not a clean metadata result.
    check("UNKNOWN_XATTR_TOOL_UNAVAILABLE", 1)

    getfattr = tool / "getfattr"
    getfattr.write_text('#!/bin/sh\nexit "${E2631_XATTR_RC:-0}"\n')
    getfattr.chmod(0o755)
    check("NO_DETECTED_SPECIAL_METADATA_NOT_MIGRATION_APPROVAL", 0)
    env["E2631_XATTR_RC"] = "1"
    check("UNKNOWN_XATTR_READ_FAILED", 1)

    # Old migration interface must refuse even when given arbitrary paths.
    marker = path / "must-not-write"
    proc = subprocess.run(["sh", str(migrate), "--stage", str(upper), str(marker)], capture_output=True, text=True)
    assert proc.returncode != 0 and "REFUSED_MIGRATION_NOT_METADATA_SAFE" in proc.stdout
    assert not marker.exists()

print("PASS: unknown metadata is never treated as copy approval; migration fails closed")
