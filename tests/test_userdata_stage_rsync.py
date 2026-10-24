"""Isolated offline staging tests: every path is redirected into temp files."""
from pathlib import Path
import os
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[1]
source = (repo / "overlay/target/linux/sanechips/base-files/sbin/e2631-userdata-stage-rsync").read_text()
audit = repo / "overlay/target/linux/sanechips/base-files/sbin/e2631-extroot-audit"

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    jffs2 = root / "jffs2"
    src = jffs2 / "upper"
    ubifs = root / "ubifs"
    for folder in (src, ubifs, root / "ubi0", root / "ubi0_0", root / "mtd10", root / "tools"):
        folder.mkdir(parents=True, exist_ok=True)
    (root / "mtd10" / "name").write_text("userdata\n")
    (root / "mtd10" / "size").write_text("49283072\n")
    (root / "ubi0" / "mtd_num").write_text("10\n")
    (root / "ubi0_0" / "name").write_text("userdata\n")
    mounts = root / "mounts"
    mounts.write_text(f"/dev/mtd8 {jffs2} jffs2 ro 0 0\n/dev/ubi0_0 {ubifs} ubifs rw 0 0\n")
    changes = {
        "/proc/mounts": str(mounts),
        "/sys/class/mtd/mtd10": str(root / "mtd10"),
        "/sys/class/ubi/ubi0/mtd_num": str(root / "ubi0" / "mtd_num"),
        "/sys/class/ubi/ubi0_0/name": str(root / "ubi0_0" / "name"),
    }
    for old, new in changes.items():
        assert old in source
        source = source.replace(old, new)
    script = root / "stage"
    script.write_text(source)
    fake = root / "tools" / "rsync"
    fake.write_text(
        '#!/bin/sh\n'
        'if [ "${1:-}" = "--version" ]; then echo "rsync 3.5.1: ACLs, xattrs"; exit 0; fi\n'
        'if [ "${E2631_FAIL_COPY:-}" = 1 ]; then exit 1; fi\n'
        'exit 0\n'
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(root / "tools") + os.pathsep + env["PATH"]
    env.pop("E2631_CONFIRM", None)

    def run(mode, **vars):
        e = env.copy()
        e.update(vars)
        return subprocess.run(["/bin/sh", str(script), mode, str(src), str(ubifs)],
                              env=e, capture_output=True, text=True)

    p = run("--plan")
    assert p.returncode == 0 and "DRY_RUN_ONLY" in p.stdout and not list(ubifs.iterdir()), p
    p = run("--stage")
    assert p.returncode == 3 and "REFUSED_NO_EXPLICIT_CONFIRMATION" in p.stdout
    assert not list(ubifs.iterdir())

    p = run("--stage", E2631_CONFIRM="STAGE_ONLY_NEVER_ACTIVATE", E2631_FAIL_COPY="1")
    assert p.returncode != 0 and "FAILED_COPY_TRANSACTION_RETAINED" in p.stdout
    assert (ubifs / ".e2631-txn").is_dir()
    q = subprocess.run(["/bin/sh", str(audit), "--inspect-dir", str(ubifs)],
                       capture_output=True, text=True)
    assert q.returncode != 0 and "INCOMPLETE_TRANSACTION" in q.stdout

    # A separate fresh destination with simulated successful rsync must still
    # retain the intent journal and must not create a ready/activation marker.
    ubifs2 = root / "ubifs2"
    ubifs2.mkdir()
    mounts.write_text(
        f"/dev/mtd8 {jffs2} jffs2 ro 0 0\\n"
        f"/dev/ubi0_0 {ubifs2} ubifs rw 0 0\\n"
    )
    p = subprocess.run(
        ["/bin/sh", str(script), "--stage", str(src), str(ubifs2)],
        env={**env, "E2631_CONFIRM": "STAGE_ONLY_NEVER_ACTIVATE"},
        capture_output=True, text=True,
    )
    assert p.returncode == 0 and "STAGED_UNVERIFIED_NOT_COMMITTED" in p.stdout, p
    assert (ubifs2 / ".e2631-txn" / "upper").is_dir()
    assert not (ubifs2 / ".e2631-extroot-ready").exists()
    q = subprocess.run(["/bin/sh", str(audit), "--inspect-dir", str(ubifs2)],
                       capture_output=True, text=True)
    assert q.returncode != 0 and "INCOMPLETE_TRANSACTION" in q.stdout

print("PASS: staging is guarded and never activates an incomplete transaction")
