"""Fail-closed content and metadata comparison, without device access."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
compare = repo / "tools/compare_overlay_upper.py"

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    src = root / "source"
    dst = root / "dest"
    src.mkdir()
    (src / "config").write_bytes(b"configuration")
    (src / "link").symlink_to("config")
    shutil.copytree(src, dst, symlinks=True)

    def run(expected):
        p = subprocess.run([sys.executable, str(compare), str(src), str(dst)],
                           capture_output=True, text=True)
        assert p.returncode == expected, (p.stdout, p.stderr)
        return p

    assert "MATCH_METADATA_AND_CONTENT_ONLY" in run(0).stdout

    (dst / "config").write_bytes(b"corruption!")
    assert "sha256" in run(1).stdout
    shutil.copy2(src / "config", dst / "config")
    run(0)

    (dst / "link").unlink()
    (dst / "link").symlink_to("unexpected")
    assert "target" in run(1).stdout
    (dst / "link").unlink()
    (dst / "link").symlink_to("config")

    # Replacing a symlink modifies the parent directory metadata.
    shutil.copystat(src, dst, follow_symlinks=False)
    run(0)

    # User xattrs are supported on ordinary Linux temp files in CI.
    os.setxattr(src / "config", "user.e2631_test", b"preserved")
    assert "xattrs" in run(1).stdout
    os.setxattr(dst / "config", "user.e2631_test", b"preserved")
    run(0)

    # Hardlinks must retain link identity, not just matching contents.
    os.link(src / "config", src / "duplicate")
    shutil.copy2(src / "config", dst / "duplicate")
    shutil.copystat(src, dst, follow_symlinks=False)
    assert "DIFFERENT:HARDLINK_GROUPS" in run(1).stdout

print("PASS: metadata, xattrs, symlink and hardlink mismatches reject migration")
