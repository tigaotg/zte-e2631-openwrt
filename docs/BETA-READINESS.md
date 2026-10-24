# E2631 public Beta readiness (work in progress)

**Status: development branch only. Not a flashable release.**

Base: `handoff/consolidated-2026-10-20` at `45be294`.
Development branch: `beta/public-readiness`.

## What is changed

- Fresh factory wireless setup no longer automatically broadcasts an unencrypted
  `OpenWrt` SSID. Provision Wi-Fi explicitly from a secured wired administrator
  session. The manual `e2631-wifi-ap` command still supports an explicit open
  SSID; never recommend it on an untrusted network.
- `e2631-wifi-ap` rejects invalid nonempty WPA2 passwords instead of silently
  converting the request to an open network.
- GitHub Actions run source checks and isolated userdata initializer tests.
  These checks do **not** build, flash, or certify firmware.

## Release blockers

1. **Extroot activation gate**: ROM fstab currently enables `/dev/ubi0_0`
   unconditionally. Do not activate newly created/partially migrated volumes.
   Preserve upgrade compatibility with devices already using UBIFS; never erase
   or automatically initialize userdata during boot. This requires a migration
   and power-loss recovery design and real hardware acceptance tests.
2. **Wi-Fi**: independently repeat full cold-power boots, successful client
   associations, multi-client transfers and long-running stability tests.
   Earlier association hard hangs and cold-bind hangs remain open.
3. **Hardware variants**: verify board revision, NAND ID, geometry, factory
   package header compatibility and A/B rollback behavior on each supported
   variant. Unsupported variants must be explicitly excluded.
4. **First-install and upgrade paths**: test blank userdata, preinitialized
   userdata, legacy JFFS2 configuration, preserve-settings upgrade and
   interrupted migration with serial recovery available.
5. **Build provenance**: record pinned base commit, kit commit, package
   manifest, hashes, reproducible build instructions, and independent package
   verification. A passing CI job is not a release approval.
6. **No release credentials**: check sources and binary artifacts for secrets,
   personal settings, copied NAND images and manufacturer credentials.

## Acceptance protocol before a public downloadable Beta

- Two separate known-good devices if possible, with their hardware revisions
  and SPI-NAND IDs recorded, each with a verified recovery route.
- Record at least ten full power-off cold starts per supported board variant;
  validate two bands, WPA2 association and 30-minute traffic; record every
  hang or recovery. This is a suggested test target, not an accomplished result.
- Run initial install and upgrade/rollback with `dmesg`, UART transcripts,
  MTD layout and before/after configuration checks; do not treat a mock test
  as a NAND test.
- Review all unresolved blockers, then mark a **pre-release** on GitHub with
  checksum, compatible variants, known issues and recovery instructions.
  Never mark this branch or untested binaries as Stable.

## Current conclusion

The source changes lower a known security risk; they do not establish device
safety or general compatibility. **Do not distribute a binary from this
branch for casual flashing yet.**

## Extroot audit development progress

A new read-only `e2631-extroot-audit --inspect-dir PATH` distinguishes
uninitialized data, partial `upper/work` layouts, stale staging directories,
nonempty work directories, legacy candidates and explicitly marked candidates.
The audit intentionally **does not authorize activation**: it is a directory
structure check, not proof of correct UBI geometry, metadata fidelity, or
power-loss atomicity. There is no boot-time invocation or automatic NAND write.

The proposed `.e2631-extroot-ready` marker remains **unissued**. A safe
producer needs a validated, metadata-preserving migration and a crash-safe
commit protocol. Existing UBIFS installations may lack this marker, so any
future boot activation rule must include a tested legacy compatibility path.

The existing ROM `fstab enabled '1'` is still unresolved and prevents release.
Never tell users that passing this mock test makes the current image safe to flash.
