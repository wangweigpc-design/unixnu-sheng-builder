"""Split an already encrypted stream into release assets below the per-file limit."""
import hashlib
import json
from pathlib import Path
import sys

folder = Path("encrypted-release")
folder.mkdir(exist_ok=True)
limit = 1024 ** 3
records = []
index = 0
while True:
    first = sys.stdin.buffer.read(1024 * 1024)
    if not first:
        break
    name = f"bundle.tar.zst.age.part{index:03d}"
    size = 0
    digest = hashlib.sha256()
    with (folder / name).open("xb") as output:
        chunk = first
        while chunk:
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
            if size == limit:
                break
            chunk = sys.stdin.buffer.read(min(1024 * 1024, limit - size))
    records.append({"name": name, "bytes": size, "sha256": digest.hexdigest()})
    index += 1
if not records:
    raise SystemExit("Refusing to publish an empty encrypted stream")
(folder / "encrypted-manifest.json").write_text(json.dumps(records, indent=2) + "\n")
print(f"Created {len(records)} encrypted release parts.")
