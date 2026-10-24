"""Mock the read-only preflight without opening any real NAND device."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "overlay/target/linux/sanechips/base-files/sbin/e2631-extroot-preflight").read_text()

with tempfile.TemporaryDirectory() as folder:
    temp = Path(folder)
    sysmtd = temp / "mtd10"
    ubi = temp / "ubi"
    tools = temp / "tools"
    for p in (sysmtd, ubi / "ubi0", ubi / "ubi0_0", tools):
        p.mkdir(parents=True, exist_ok=True)
    for name, value in {"name": "userdata", "size": "49283072", "erasesize": "131072"}.items():
        (sysmtd / name).write_text(value + "\n")
    (ubi / "ubi0" / "mtd_num").write_text("10\n")
    (ubi / "ubi0_0" / "name").write_text("userdata\n")
    mounts = temp / "mounts"
    mounts.write_text("")
    log = temp / "calls"
    log.write_text("")
    auditor = tools / "audit"
    auditor.write_text('#!/bin/sh\necho "CANDIDATE_ONLY"\n')
    auditor.chmod(0o755)
    for command in ("mount", "umount"):
        fake = tools / command
        fake.write_text(
            '#!/bin/sh\n'
            'echo "' + command + ' $*" >> "$E2631_TEST_LOG"\n'
            'if [ "' + command + '" = mount ] && [ "${E2631_FAIL_MOUNT:-0}" = 1 ]; '
            'then exit 1; fi\n'
        )
        fake.chmod(0o755)
    changes = {
        "/sys/class/mtd/mtd10": str(sysmtd),
        "/sys/class/ubi/ubi0/mtd_num": str(ubi / "ubi0" / "mtd_num"),
        "/sys/class/ubi/ubi0_0/name": str(ubi / "ubi0_0" / "name"),
        "/dev/ubi0_0": str(temp / "fakeubi"),
        "[ -c ": "[ -e ",
        "/sbin/e2631-extroot-audit": str(auditor),
        "/proc/mounts": str(mounts),
    }
    (temp / "fakeubi").touch()
    for old, new in changes.items():
        assert old in source, old
        source = source.replace(old, new)
    script = temp / "preflight"
    script.write_text(source)

    env = os.environ.copy()
    env["PATH"] = str(tools) + os.pathsep + env["PATH"]
    env["E2631_TEST_LOG"] = str(log)

    def run(**changes):
        e = env.copy()
        e.update(changes)
        return subprocess.run(["sh", str(script), "--inspect"], env=e, capture_output=True, text=True)

    result = run()
    assert result.returncode == 0, result
    assert "CANDIDATE_ONLY" in result.stdout
    calls = log.read_text().splitlines()
    assert len(calls) == 2 and calls[0].startswith("mount -t ubifs -o ro ") and calls[1].startswith("umount "), calls

    log.write_text("")
    result = run(E2631_FAIL_MOUNT="1")
    assert result.returncode != 0 and "REFUSED_READONLY_MOUNT_FAILED" in result.stdout, result
    assert not any(x.startswith("umount ") for x in log.read_text().splitlines())

    log.write_text("")
    (ubi / "ubi0" / "mtd_num").write_text("9\n")
    result = run()
    assert result.returncode != 0 and "REFUSED_UBI0_MAPPING" in result.stdout, result
    assert not log.read_text()

print("PASS: UBI preflight mocks never write NAND; failures stop inspection")
