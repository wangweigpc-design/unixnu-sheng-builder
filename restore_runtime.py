"""Authenticate and restore optional encrypted inputs from the same pinned build."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import urllib.request

from prepare_build import PINS, PROFILE

MAPPING = {'data_ramdisk': 'data.dbr', 'trust_cache': 'trust-cache.bin', 'gpu_addon': 'gpu-addon.bin'}


def validate(directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    if manifest['profile'] != PROFILE or manifest['pins'] != PINS or manifest['data_gib'] != 210:
        raise ValueError('Runtime cache belongs to different build inputs')
    if set(manifest['inputs']) != set(MAPPING):
        raise ValueError('Incomplete runtime cache')
    for key, name in MAPPING.items():
        item = manifest['inputs'][key]
        path = directory/name
        if item['file'] != name or path.stat().st_size != item['bytes']:
            raise ValueError('Runtime input size/name mismatch')
        with path.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != item['sha256']:
                raise ValueError('Runtime input checksum mismatch')
    with (directory/'data.dbr').open('rb') as handle:
        header = handle.read(32)
    if struct.unpack_from('<8sIIQ', header) != (b'DBRDISK1', 1, 4096, 210*2**30):
        raise ValueError('Runtime cache is not the full-capacity seed')
    return manifest


def main():
    release = os.environ.get('RUNTIME_CACHE_RELEASE', '')
    if not release:
        print('No runtime cache selected; a fresh runtime will be built.')
        return
    digest = os.environ.get('RUNTIME_CACHE_SHA256', '')
    identity = os.environ.get('RUNTIME_CACHE_AGE_IDENTITY', '')
    if not re.fullmatch(r'runtime-cache-[0-9]+', release) or not re.fullmatch(r'[a-f0-9]{64}', digest) or not identity:
        raise ValueError('Invalid runtime cache settings')
    target = Path('UniXNU/out/sheng')/PROFILE/'sheng_macos/runtime'
    with tempfile.TemporaryDirectory(prefix='runtime-cache-') as temporary:
        base = Path(temporary)
        key = base/'identity.age'
        key.write_text(identity)
        key.chmod(0o600)
        encrypted = base/'runtime.tar.gz.age'
        url = f'https://github.com/wangweigpc-design/unixnu-sheng-builder/releases/download/{release}/runtime.tar.gz.age'
        check, total = hashlib.sha256(), 0
        with urllib.request.urlopen(url, timeout=90) as response, encrypted.open('wb') as handle:
            while data := response.read(2**20):
                total += len(data)
                if total > 128*2**20:
                    raise ValueError('Runtime cache download exceeds limit')
                check.update(data)
                handle.write(data)
        if check.hexdigest() != digest:
            raise ValueError('Encrypted runtime cache checksum mismatch')
        archive = base/'runtime.tar.gz'
        subprocess.run(['age', '-d', '-i', str(key), '-o', str(archive), str(encrypted)], check=True)
        extracted = base/'extracted'
        extracted.mkdir()
        seen, total = set(), 0
        allowed = {'manifest.json', *MAPPING.values()}
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                if member.name not in allowed or member.name in seen or not member.isfile():
                    raise ValueError('Invalid runtime cache archive member')
                total += member.size
                if total > 512*2**20 or member.size < 0:
                    raise ValueError('Expanded runtime cache exceeds limit')
                seen.add(member.name)
                with tar.extractfile(member) as source, (extracted/member.name).open('xb') as output:
                    shutil.copyfileobj(source, output, 2**20)
        if seen != allowed:
            raise ValueError('Missing runtime cache member')
        manifest = validate(extracted)
        if release != 'runtime-cache-'+manifest['source_run']:
            raise ValueError('Runtime cache run mismatch')
        target.mkdir(parents=True, exist_ok=True)
        if any((target/name).exists() for name in MAPPING.values()):
            raise ValueError('Refusing to replace existing runtime files')
        for name in MAPPING.values():
            shutil.copy2(extracted/name, target/name)
        options = {key: str((target/name).resolve()) for key, name in MAPPING.items()}
        Path('reports/resume-options.json').write_text(json.dumps(options, indent=2)+'\n')
        Path('reports/resumed-runtime.json').write_text(json.dumps(manifest, indent=2)+'\n')
        print('Restored authenticated runtime inputs; source build and image checks remain required.')


if __name__ == '__main__':
    main()
