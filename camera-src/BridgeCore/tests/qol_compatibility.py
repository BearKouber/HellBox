import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zlib


parser = argparse.ArgumentParser()
parser.add_argument("qol", type=Path)
parser.add_argument("camera", type=Path)
parser.add_argument("recorder", type=Path)
parser.add_argument("captain", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
environment = dict(os.environ, APPDATA=str((args.output / "appdata").resolve()))
bundle = "9e13b2414b41b842"
boot_id = bytes.fromhex("e217d12cfa8d4ea181dcbd8a618a0437")
qol = (args.qol / bundle).read_bytes()
vanilla = (args.qol / (bundle + ".orig")).read_bytes()
checks = []


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unpack(data):
    magic, size, reserved = struct.unpack_from("<III", data)
    assert magic == 0xF0000004 and reserved == 0
    raw = bytearray()
    offset = 12
    while len(raw) < size:
        length = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        block = data[offset:offset + length]
        raw.extend(block if length == 65536 else zlib.decompress(block))
        offset += length
    assert offset == len(data)
    return bytes(raw[:size])


def pack(raw):
    data = bytearray(struct.pack("<III", 0xF0000004, len(raw), 0))
    for offset in range(0, len(raw), 65536):
        block = raw[offset:offset + 65536].ljust(65536, b"\0")
        compressed = zlib.compress(block)
        chosen = compressed if len(compressed) < 65536 else block
        data.extend(struct.pack("<I", len(chosen)))
        data.extend(chosen)
    return bytes(data)


def records(data):
    raw = unpack(data)
    count = struct.unpack_from("<I", raw)[0]
    offset = 260 + count * 16
    result = {}
    for index in range(count):
        identifier = raw[offset:offset + 16]
        assert identifier == raw[260 + 16 * index:276 + 16 * index]
        length = struct.unpack_from("<I", raw, offset + 28)[0]
        result[identifier] = raw[offset:offset + length + 36]
        offset += length + 36
    assert len(result) == count and offset == len(raw)
    return result


def game(name, source=qol):
    path = args.output / name
    contents = path / "contents"
    contents.mkdir(parents=True)
    (contents / bundle).write_bytes(source)
    (contents / "settings.ini").write_text(
        'boot_package = "resource_packages/boot"\nboot_script = "lua/boot/boot"\n', encoding="utf-8")
    shutil.copyfile(args.qol / "9cf71054ea26dddf", contents / "9cf71054ea26dddf")
    return path


def run(executable, command, path, *extra, success=True):
    result = subprocess.run([str(executable.resolve()), command, str(path.resolve()), *map(str, extra)],
                            env=environment, capture_output=True)
    assert (result.returncode == 0) == success, (result.stdout, result.stderr)
    return result


def current(path):
    return (path / "contents" / bundle).read_bytes()


def store(path):
    return path / "helldivers_bridge_v1" / bundle


def manifest(path):
    return store(path) / (digest(current(path)) + ".manifest")


def modules(path):
    lines = manifest(path).read_text(encoding="utf-8").splitlines()
    return dict(line.split() for line in lines[3:])


path = game("qol-lifecycle")
run(args.camera, "prepare", path, path / "prepared")
prepared = (path / "prepared" / bundle).read_bytes()
before, after = records(qol), records(prepared)
assert before.keys() == after.keys()
assert [identifier for identifier in before if before[identifier] != after[identifier]] == [boot_id]
run(args.camera, "install", path)
assert current(path) == prepared
run(args.camera, "install", path)
assert current(path) == prepared
camera_hash = modules(path)["camera"]
run(args.recorder, "install", path)
recorder_hash = modules(path)["recorder"]
run(args.captain, "install", path)
assert modules(path)["camera"] == camera_hash and modules(path)["recorder"] == recorder_hash
assert len(modules(path)) == 3
run(args.camera, "uninstall", path)
assert set(modules(path)) == {"captain", "recorder"}
run(args.recorder, "uninstall", path)
run(args.captain, "uninstall", path)
assert current(path) == qol
assert (store(path) / (digest(qol) + ".original")).read_bytes() == qol
checks.append("QoL prepare/install/reinstall, three modules, independent uninstall, exact QoL restore")

path = game("old-backup-and-mod-replacement", vanilla)
run(args.camera, "install", path)
versioned = store(path) / (digest(vanilla) + ".original")
versioned.unlink()
run(args.camera, "install", path)
assert versioned.read_bytes() == vanilla
(path / "contents" / bundle).write_bytes(qol)
run(args.camera, "install", path)
assert (path / "captain_bridge_backup" / (bundle + ".original")).read_bytes() == vanilla
run(args.camera, "uninstall", path)
assert current(path) == qol
checks.append("old HDB1 recovery fallback and QoL replacement preserve old backup but restore QoL")

path = game("missing-recovery", vanilla)
run(args.camera, "install", path)
(path / "contents" / bundle).write_bytes(qol)
run(args.camera, "install", path)
saved = current(path)
(store(path) / (digest(qol) + ".original")).unlink()
run(args.camera, "install", path, success=False)
assert current(path) == saved
checks.append("missing QoL recovery refuses mismatched legacy vanilla backup")

path = game("corrupt-module")
run(args.camera, "install", path)
saved = current(path)
(store(path) / (modules(path)["camera"] + ".luac")).write_bytes(b"corrupt")
run(args.camera, "install", path, success=False)
assert current(path) == saved
checks.append("corrupt module rejected without touching game bundle")

raw = unpack(qol)
boot_bytes = records(qol)[boot_id]
boot_offset = raw.index(boot_bytes)
changed = bytearray(raw)
changed[boot_offset + 44 + 10] ^= 1
path = game("unknown-boot", pack(changed))
saved = current(path)
run(args.camera, "prepare", path, path / "prepared", success=False)
assert current(path) == saved
path = game("trailing-data", qol + b"extra")
run(args.camera, "prepare", path, path / "prepared", success=False)
checks.append("unknown boot script and invalid container refused")

changed = bytearray(raw)
other = next(record for identifier, record in records(qol).items() if identifier != boot_id)
changed[raw.index(other) + len(other) - 1] ^= 1
variant = pack(changed)
path = game("nonboot-mod-variant", variant)
run(args.camera, "install", path)
run(args.camera, "uninstall", path)
assert current(path) == variant
checks.append("nonboot resource variation accepted and exactly restored, not a full bundle allowlist")

path = game("manifest-content-mismatch")
run(args.camera, "install", path)
text = manifest(path).read_text(encoding="utf-8")
installed = bytearray(unpack(current(path)))
installed[installed.index(other) + len(other) - 1] ^= 1
modified = pack(installed)
old_hash = digest(current(path))
(path / "contents" / bundle).write_bytes(modified)
run(args.camera, "install", path, success=False)
manifest(path).write_text(text.replace(old_hash, digest(modified)), encoding="utf-8")
run(args.camera, "install", path, success=False)
assert current(path) == modified
checks.append("foreign changes with a bridge rejected, even with a rekeyed manifest")

report = {"qol_sha256": digest(qol), "checks": checks, "unchanged_resources": len(before) - 1,
          "runtime_tested": False}
(args.output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
