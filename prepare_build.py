"""Apply narrowly checked full-capacity and first-login settings to pinned sources."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

PROFILE = "macos-27.3-26C5035r"
PINS = {
    "UniXNU": "21d683dff61c66f219f03ab9d8b9249026514788",
    "device": "bc05635a483d69a6c51cafd44723372b66c941f3",
    "uefi-sheng": "8156d2e54a9f57818dc8b415a1a7dc28ad9ba4be",
}
STORAGE_GOOD_REVISION = "d7c7aee91fe740f5b986165312aa7044cd09dfd4"


def recover_storage_start():
    """Recover the removed function tail from its last complete source revision."""
    path = Path('device/package/SourceStorage.cpp')
    current = path.read_text()
    assert hashlib.sha256(current.encode()).hexdigest() == '7811e0fc636abfeced1b067d2b4dac669e000bb2a11a8b7b3b570ce2b0a5caa8'
    subprocess.run(['git', '-C', 'device', 'fetch', '--depth=1', 'origin', STORAGE_GOOD_REVISION], check=True)
    original = subprocess.check_output(['git', '-C', 'device', 'show',
                                        STORAGE_GOOD_REVISION+':package/SourceStorage.cpp']).decode()
    assert hashlib.sha256(original.encode()).hexdigest() == '603e6ce031d6a2e384a6fbd1532563bb7eec037d30e5a019ca513ca2d213e85d'
    marker = '    attempted = true;\n'
    assert current.endswith(marker) and original.count(marker) == current.count(marker) == 1
    tail = original.split(marker, 1)[1]
    assert tail.endswith('    ufsBench();\n}\n')
    # The new helpers only emit diagnostics when storage-probe=1; the normal
    # boot path retains the complete authenticated storage startup sequence.
    repaired = current + tail
    repaired = repaired.replace(marker, marker+'    startup_probe_start();\n    startup_mark("begin");\n')
    repaired = repaired.replace('    ufsBench();\n}', '    ufsBench();\n    startup_mark("ready");\n}')
    without_probes = repaired.replace('    startup_probe_start();\n    startup_mark("begin");\n', '').replace('    startup_mark("ready");\n', '')
    assert without_probes == current+tail
    tokens = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', '', repaired, flags=re.S)
    assert tokens.count('{') == tokens.count('}')
    path.write_text(repaired)
    record = Path('device/porting.toml')
    text = record.read_text()
    start = text.index('id = "storage"')
    end = text.index('\n[[area]]', start)
    block = text[start:end]
    finding = re.search(r'^findings = (\[.*\])$', block, re.M)
    assert finding is not None
    findings = tomllib.loads('findings = '+finding[1])['findings']
    findings.append('The full-capacity builder restores the SourceStorage startup tail removed by 60566370 from complete revision '+STORAGE_GOOD_REVISION+'. IOStorageFamily/APFS loading, policy authentication, class registration, UFS and Data startup are preserved. Current BootTime conversions remain; storage-probe checkpoints are optional. Hardware qualification is pending.')
    block = block[:finding.start()]+ 'findings = '+json.dumps(findings)+block[finding.end():]
    record.write_text(text[:start]+block+text[end:])


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"Pinned source does not match expected edit: {path}")
    path.write_text(text.replace(old, new))


def configure_reference_build():
    path = Path('UniXNU/scripts/build-fileset-release-reference.py')
    # Match the main kernel's IOKit ABI selection. Both profiles deliberately
    # retain the iOS object platform; macOS selects the padded kext vtables via
    # XNU_TARGET_OS_OSX, exactly as build-xnu-4k-baseline.sh does.
    replace_once(path, "    mode = 'lto' if options.lto else 'snapshot'\n", """    target = os.environ.get('UNIXNU_XNU_TARGET', 'ios')
    target_defines = {'ios': '-DXNU_TARGET_OS_IOS', 'macosx': '-DXNU_TARGET_OS_OSX'}
    if target not in target_defines:
        raise ValueError('UNIXNU_XNU_TARGET must be ios or macosx')
    target_define = target_defines[target]
    mode = 'lto' if options.lto else 'snapshot'
""")
    replace_once(path, "        'mode': mode,\n", "        'mode': mode,\n        'target': target,\n")
    replace_once(path, ' -DXNU_TARGET_OS_IOS\',', ' {target_define}\',')
    # This auxiliary build had an independent hard-coded eight-job setting.
    # Honour the same bounded parallelism as the main kernel build.
    replace_once(path, "'BUILD_WERROR=0','MAKEJOBS=-j8',",
                 "'BUILD_WERROR=0',f'MAKEJOBS=-j{int(os.environ.get(\"JOBS\", \"2\"))}',")
    # The macOS outside-memory probe calls add_saved_state_pc, whose original
    # authenticated implementation is feature-gated in the Apple header. The
    # DEVELOPMENT build exposes it, but the RELEASE comparison build does not.
    # Enable that same helper only in the isolated, non-booted comparison copy;
    # retain its original PAC validation and signed-thread-state manipulation.
    replace_once(path, '-DXNU_SOURCE_CORECRYPTO14=1 -DXNU_BOOT_PROGRESS=0',
                 '-DXNU_SOURCE_CORECRYPTO14=1 -DXNU_BOOT_PROGRESS=0 -DUNIXNU_REFERENCE_MEMORY_PROBE=1')
    # Newly added weak board diagnostics also appear in this comparison build.
    # Extend its existing native-hook stubs only to board diagnostic names;
    # the real booted kernel still links their implementations from the board.
    replace_once(path, 'native_[a-z0-9_]+|boot_log_rounds|boot_cache_input_capture',
                 'native_[a-z0-9_]+|boot_log_[a-z0-9_]+|boot_cache_input_capture|sheng_boot_watchdog_policy')
    marker = "        manifest = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()\n"
    replace_once(path, marker, '''        thread_status = source / 'osfmk/mach/arm/thread_status.h'
        thread_text = thread_status.read_text()
        guard = '#if HAS_ADD_SAVED_STATE_PC\\n'
        if thread_text.count(guard) != 1:
            raise RuntimeError('Pinned saved-state helper guard changed')
        thread_status.write_text(thread_text.replace(guard,
            '#if HAS_ADD_SAVED_STATE_PC || defined(UNIXNU_REFERENCE_MEMORY_PROBE)\\n'))
'''+marker)
    marker = "    build_log = (output / f'{mode}-build.log').read_text()\n"
    replace_once(path, marker, marker+'''    required_list = output / f'{mode}-obj/RELEASE_ARM64_BCM2837' / ('nonltolink.filelist' if options.lto else 'link.filelist')
    if not required_list.is_file():
        lines = build_log.splitlines()
        failures = [i for i, line in enumerate(lines) if re.search(r'error:|fatal error|Killed|Error [0-9]', line)]
        for i in failures[:16]:
            print('\\n'.join(lines[max(0, i-2):i+5]), flush=True)
        print('\\n'.join(lines[-40:]), flush=True)
        raise RuntimeError('RELEASE reference compilation did not reach its link file list; see compiler diagnostics above')
''')
    replace_once(path, "    if result.returncode:\n        raise SystemExit(result.returncode)\n",
                 "    if result.returncode:\n        print((output / f'{mode}-build.log').read_text()[-24000:], flush=True)\n        raise SystemExit(result.returncode)\n")


def main():
    for directory, revision in PINS.items():
        actual = subprocess.check_output(["git", "-C", directory, "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise RuntimeError(f"Unexpected source revision in {directory}")
    for key in ("UNIXNU_UNIQUE_CHIP_ID", "UNIXNU_LAB_PASSWORD", "ARTIFACT_AGE_RECIPIENT"):
        if not os.environ.get(key):
            raise RuntimeError(f"Required private build input is missing: {key}")
    seed = os.environ["UNIXNU_UNIQUE_CHIP_ID"]
    try:
        number = int(seed, 0)
    except ValueError:
        number = int(seed, 16)
    for representation in {seed, str(number), hex(number), format(number, "x"), format(number, "X")}:
        print("::add-mask::" + representation)

    board = Path("device/board.toml")
    replace_once(board, '"max_image_bytes" = 202375168', '"max_image_bytes" = 201326592')
    replace_once(board, f'["os_overrides"."{PROFILE}"."payload"]\n"timeout" = -1',
                 f'["os_overrides"."{PROFILE}"."payload"]\n"timeout" = 5')
    # Match the logical FAT capacity used by the current macOS lab. The
    # encoded Android image must still fit the separately enforced 192 MiB.
    replace_once(board, '"size_mib" = 187', '"size_mib" = 256')
    base_board = tomllib.loads(board.read_text())
    archives = base_board['kernel']['archives']
    old_policy = 'build-sheng-source-storage.py --policy-dir scripts/policies/ipados-27.0.1-24A446'
    assert archives.count(old_policy) == 1
    archives = [entry.replace(old_policy, f'build-sheng-source-storage.py --policy-dir scripts/policies/{PROFILE}')
                for entry in archives]
    with board.open("a") as output:
        output.write(f'\n[os_overrides."{PROFILE}".kernel]\n'
                     'config_fragments = ["arch:configs/common.config", "os:configs/macos.config"]\n'
                     'archives = ' + json.dumps(archives) + '\n')
    parsed = tomllib.loads(board.read_text())
    override = parsed["os_overrides"][PROFILE]
    assert override["payload"]["runtime"]["data_gib"] == 210
    assert override["bootimg"]["max_image_bytes"] == 201326592

    # This selected macOS profile compiles NativeAES.cpp with its Darwin 26
    # vtable fixture inside build-gop-legacy-display-27.py, then links it into
    # that adapter. Keep the source selected, but do not require a second,
    # incompatible generic iPadOS SoftwareAES archive.
    catalog = Path('UniXNU/components.toml')
    catalog_text = catalog.read_text()
    blocks = re.findall(r'\[\[component\]\]\n.*?(?=\n\[\[component\]\]|\Z)', catalog_text, re.S)
    aes_blocks = [block for block in blocks if re.search(r'^id = "SoftwareAES"$', block, re.M)]
    assert len(aes_blocks) == 1 and aes_blocks[0].count('build_stage = "kernel"') == 1
    replace_once(catalog, aes_blocks[0], aes_blocks[0].replace('build_stage = "kernel"', 'build_stage = "embedded"'))
    adapter = Path('device/scripts/build-gop-legacy-display-27.py').read_text()
    assert "drivers/SoftwareAES/NativeAES.cpp" in adapter and "-DNATIVE_AES_DARWIN26=1" in adapter
    assert 'build-gop-legacy-display-27.py' in archives
    recover_storage_start()
    configure_reference_build()

    # The upstream live-map correction is qualified only for 8 GiB. Bound
    # the static fallback to the conservative ranges verified for this
    # 12 GiB/older-firmware installation; do not broaden the 8 GiB guard.
    memory = Path('uefi-sheng/Platforms/Xiaomi/shengPkg/Library/MemoryMapLib/MemoryMapLib.c')
    memory_ranges = [
        ('DRAM bank 1 low', '0x880000000, 0x3B300000', '0x880000000, 0x39D00000'),
        ('DRAM gap 0xCCF80000', '0xCCF80000, 0x0B080000', '0xCCF80000, 0x07D80000'),
        ('DRAM gap 0xE671D000', '0xE671D000, 0x190E3000', '0xE7CB0000, 0x17B50000'),
    ]
    for label, before, after in memory_ranges:
        replace_once(memory, '{"' + label + '", ' + before + ',', '{"' + label + '", ' + after + ',')

    # The pinned installer accidentally shadows the imported CLI parser.
    installer = Path("device/scripts/prepare-macos-install.py")
    replace_once(installer, "from unixnu.cli import parser, prepare", "from unixnu.cli import parser as cli_parser, prepare")
    replace_once(installer, "ctx = Context(parser().parse_args(", "ctx = Context(cli_parser().parse_args(")
    replace_once(installer, "{'name': 'unixnu', 'password': password}", "{'name': 'xiaomi', 'password': password}")

    seed_tool = Path("UniXNU/scripts/make-macos-data-seed.py")
    replace_once(seed_tool, "    prefs['autoLoginUser'] = name\n", """    prefs['autoLoginUser'] = name
    prefs['autoLoginUserScreenLocked'] = False
    global_path = mount / 'Library/Preferences/.GlobalPreferences.plist'
    global_prefs = plistlib.loads(global_path.read_bytes()) if global_path.is_file() else {}
    global_prefs.update(AppleLanguages=['en-US'], AppleLocale='en_US')
    write_root(global_path, plistlib.dumps(global_prefs, fmt=plistlib.FMT_BINARY), 0o644)
""")
    report = {"profile": PROFILE, "pins": PINS, "root_partition": "userdata",
              "data_gib": 210, "boot_max_bytes": 201326592, "initial_language": "en-US",
              "auto_login": True, "hardware_tested": False,
              "software_aes": "Darwin 26 fixture in build-gop-legacy-display-27.py",
              "root_policy_profile": PROFILE, "payload_logical_mib": 256,
              "firmware_static_memory_corrected": True, "firmware_memory_ranges": memory_ranges}
    report['source_storage_restored_from'] = STORAGE_GOOD_REVISION
    report['release_reference_jobs'] = int(os.environ.get('JOBS', '2'))
    report['release_reference_saved_pc_helper'] = 'Original authenticated helper enabled only in the isolated comparison source copy'
    report['release_reference_target'] = 'Matches UNIXNU_XNU_TARGET and the main kernel IOKit ABI; target included in cache identity'
    Path("reports").mkdir(exist_ok=True)
    Path("reports/build-plan.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Prepared pinned full-capacity sources and fresh English automatic-login seed settings.")


if __name__ == "__main__":
    main()
