"""Exercise crash boundaries in the prospective extroot activation protocol.

This is a filesystem model only, not a UBIFS durability or NAND power-cut test.
"""
from pathlib import Path
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[1]
auditor = repo / "overlay/target/linux/sanechips/base-files/sbin/e2631-extroot-audit"

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp) / "userdata"
    root.mkdir()

    def status():
        p = subprocess.run(["/bin/sh", str(auditor), "--inspect-dir", str(root)],
                           capture_output=True, text=True)
        return p.stdout.strip(), p.returncode

    assert status() == ("UNINITIALIZED", 1)
    txn = root / ".e2631-txn"
    txn.mkdir()
    assert status() == ("INCOMPLETE_TRANSACTION", 1)

    # Copy in progress, power loss before promotion.
    stage_upper = txn / "upper"
    stage_upper.mkdir()
    (stage_upper / "settings").write_text("copy in progress")
    assert status() == ("INCOMPLETE_TRANSACTION", 1)

    # Promoting one directory must not enable an overlay by itself.
    stage_upper.rename(root / "upper")
    assert status() == ("INCOMPLETE_TRANSACTION", 1)
    (root / "work").mkdir()
    assert status() == ("INCOMPLETE_TRANSACTION", 1)

    # Even a ready marker must not defeat a surviving intent journal.
    marker = root / ".e2631-extroot-ready"
    marker.write_text("e2631-extroot-v1\n")
    assert status() == ("INCOMPLETE_TRANSACTION", 1)
    txn.rmdir()

    # The final directory state is only a candidate; no boot activation.
    assert status() == ("MARKED_CANDIDATE_NEEDS_DEVICE_VALIDATION", 0)

    # Simulate truncated/invalid marker after a torn write.
    marker.write_text("e2631-extroot-")
    assert status() == ("REFUSED_INVALID_MARKER", 1)

    # No marker is ambiguous with legacy installations, not new authorization.
    marker.unlink()
    assert status() == ("LEGACY_CANDIDATE_NEEDS_DEVICE_VALIDATION", 0)

print("PASS: incomplete transaction and torn marker never count as ready")
