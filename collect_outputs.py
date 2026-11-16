"""Collect outputs and diagnostics for encryption; never publish plaintext inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

TARGET = Path("UniXNU/out/sheng/macos-27.3-26C5035r/sheng_macos")


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    elif source.is_file():
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--success", action="store_true")
    args = parser.parse_args()
    bundle = Path("private-bundle")
    bundle.mkdir(exist_ok=True)
    for source in (Path("reports"), TARGET / "logs"):
        if source.exists():
            copy(source, bundle / source.name)
    for pattern in ("build-*.log", "*.command.json"):
        for source in (TARGET / "tree/build").rglob(pattern):
            copy(source, bundle / "diagnostics" / source.relative_to(TARGET / "tree/build"))
    for directory in ("UniXNU", "device", "uefi-sheng"):
        if (Path(directory) / ".git").exists():
            result = subprocess.run(["git", "-C", directory, "diff", "--binary"], capture_output=True, check=True)
            (bundle / (directory + ".patch")).write_bytes(result.stdout)
    if args.success:
        files = ["boot/boot.img", "boot/boot.json", "runtime/data.dbr", "runtime/inputs.json",
                 "userdata/userdata-root.img", "userdata/userdata-root.json", "package.manifest.json"]
        installation = bundle / "installation"
        for relative in files:
            source = TARGET / relative
            if not source.is_file():
                raise RuntimeError(f"Required installation output missing: {source}")
            copy(source, installation / source.name)
        boot = installation / "boot.img"
        with boot.open("rb") as handle:
            boot_magic = handle.read(8)
        if boot.stat().st_size > 201326592 or boot_magic != b"ANDROID!":
            raise RuntimeError("Boot image does not fit the verified Android boot partition")
        hashes = {}
        for source in sorted(installation.iterdir()):
            with source.open("rb") as handle:
                hashes[source.name] = hashlib.file_digest(handle, "sha256").hexdigest()
        (installation / "SHA256.json").write_text(json.dumps(hashes, indent=2) + "\n")
        for source, destination in (
            (Path("device/scripts/policies/macos-27.3-26C5035r"), "root-policies"),
            (TARGET / "tree/build/verified-root-host/keys", "root-policy-private-keys"),
        ):
            if source.exists():
                copy(source, bundle / destination)
        # Only this disposable runner's downloaded IPSW cache; outputs have
        # already been collected and hashed. This makes room for encryption.
        cache = Path("UniXNU/out/ipsw").resolve()
        workspace = Path.cwd().resolve()
        if cache.is_dir() and cache.is_relative_to(workspace) and cache != workspace:
            shutil.rmtree(cache)
    (bundle / "result.json").write_text(json.dumps({
        "images_built": args.success, "hardware_tested": False,
        "run_id": os.environ.get("GITHUB_RUN_ID"), "profile": "macos-27.3-26C5035r",
    }, indent=2) + "\n")
    print("Private bundle staged for encryption.")


if __name__ == "__main__":
    main()
