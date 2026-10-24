"""Non-destructive tests for the mounted-directory Extroot policy audit."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
auditor = root / "overlay/target/linux/sanechips/base-files/sbin/e2631-extroot-audit"

with tempfile.TemporaryDirectory() as folder:
    mount = Path(folder) / "userdata"
    mount.mkdir()

    def check(expected, code):
        result = subprocess.run(
            ["sh", str(auditor), "--inspect-dir", str(mount)],
            text=True, capture_output=True, check=False
        )
        assert (result.stdout.strip(), result.returncode) == (expected, code), result

    check("UNINITIALIZED", 1)
    (mount / "upper").mkdir()
    check("INCOMPLETE_OVERLAY_LAYOUT", 1)
    (mount / "work").mkdir()
    check("LEGACY_CANDIDATE_NEEDS_DEVICE_VALIDATION", 0)
    (mount / ".e2631-stage").mkdir()
    check("INCOMPLETE_STAGING", 1)
    (mount / ".e2631-stage").rmdir()
    (mount / "work" / "dirty").write_text("pending")
    check("REFUSED_NONEMPTY_WORK", 1)
    (mount / "work" / "dirty").unlink()
    (mount / ".e2631-extroot-ready").write_text("wrong\n")
    check("REFUSED_INVALID_MARKER", 1)
    (mount / ".e2631-extroot-ready").write_text("e2631-extroot-v1\n")
    check("MARKED_CANDIDATE_NEEDS_DEVICE_VALIDATION", 0)
    (mount / ".e2631-extroot-ready").unlink()
    (mount / "upper").rmdir()
    (mount / "upper").symlink_to(mount / "work")
    check("REFUSED_SYMLINK:upper", 1)

print("PASS: read-only extroot candidate classification")
