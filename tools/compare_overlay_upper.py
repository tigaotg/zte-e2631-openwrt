#!/usr/bin/env python3
"""Read-only, fail-closed comparison of two extracted OverlayFS upper trees.

Host-side verification only: never copies, mounts, repairs or activates data.
Requires privileges sufficient to list *all* xattr namespaces on both trees.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.digest()


def snapshot(base):
    found = {}
    hardlinks = {}

    def visit(path, relative):
        st = os.lstat(path)
        mode = st.st_mode
        kind = stat.S_IFMT(mode)
        item = {
            "type": kind,
            "mode": stat.S_IMODE(mode),
            "uid": st.st_uid,
            "gid": st.st_gid,
            "mtime_ns": st.st_mtime_ns,
        }
        # Do not follow symlinks. Any unreadable attribute namespace fails
        # the whole comparison rather than silently being omitted.
        names = os.listxattr(path, follow_symlinks=False)
        item["xattrs"] = {
            key: os.getxattr(path, key, follow_symlinks=False)
            for key in names
        }
        if stat.S_ISREG(mode):
            item["length"] = st.st_size
            item["sha256"] = digest(path)
            if st.st_nlink > 1:
                hardlinks.setdefault((st.st_dev, st.st_ino), []).append(relative)
        elif stat.S_ISLNK(mode):
            item["target"] = os.readlink(path)
        elif stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            item["rdev"] = (os.major(st.st_rdev), os.minor(st.st_rdev))
        elif not stat.S_ISDIR(mode) and not stat.S_ISFIFO(mode) and not stat.S_ISSOCK(mode):
            raise ValueError(f"unknown file type: {relative}")
        found[relative] = item

        if stat.S_ISDIR(mode):
            with os.scandir(path) as entries:
                for entry in entries:
                    child = entry.name
                    if child in (".", ".."):
                        raise ValueError("invalid directory entry")
                    visit(os.path.join(path, child), f"{relative}/{child}" if relative else child)

    visit(os.fspath(base), "")
    # Canonicalize hardlink relationships independently of inode numbers.
    groups = sorted(tuple(sorted(paths)) for paths in hardlinks.values())
    return found, groups


def compare(left, right):
    source, sh = snapshot(left)
    target, th = snapshot(right)
    errors = []
    for path in sorted(source.keys() | target.keys()):
        if path not in source:
            errors.append(f"EXTRA:{path}")
        elif path not in target:
            errors.append(f"MISSING:{path}")
        else:
            for field in source[path].keys() | target[path].keys():
                if source[path].get(field) != target[path].get(field):
                    errors.append(f"DIFFERENT:{path}:{field}")
    if sh != th:
        errors.append("DIFFERENT:HARDLINK_GROUPS")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="quiesced source upper directory")
    parser.add_argument("destination", type=Path, help="staged destination upper directory")
    args = parser.parse_args()
    try:
        if not args.source.is_dir() or args.source.is_symlink():
            raise ValueError("source must be a real directory")
        if not args.destination.is_dir() or args.destination.is_symlink():
            raise ValueError("destination must be a real directory")
        differences = compare(args.source, args.destination)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"UNKNOWN_OR_UNREADABLE:{exc}", file=sys.stderr)
        return 2
    if differences:
        for line in differences[:100]:
            print(line)
        if len(differences) > 100:
            print(f"MORE_DIFFERENCES:{len(differences) - 100}")
        return 1
    print("MATCH_METADATA_AND_CONTENT_ONLY_NOT_ACTIVATION_APPROVAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
