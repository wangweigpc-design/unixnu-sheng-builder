"""Apply narrowly checked full-capacity and first-login settings to pinned sources."""
import json
import os
from pathlib import Path
import subprocess
import tomllib

PROFILE = "macos-27.3-26C5035r"
PINS = {
    "UniXNU": "21d683dff61c66f219f03ab9d8b9249026514788",
    "device": "bc05635a483d69a6c51cafd44723372b66c941f3",
    "uefi-sheng": "8156d2e54a9f57818dc8b415a1a7dc28ad9ba4be",
}


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"Pinned source does not match expected edit: {path}")
    path.write_text(text.replace(old, new))


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
    with board.open("a") as output:
        output.write(f'\n[os_overrides."{PROFILE}".kernel]\n'
                     'config_fragments = ["arch:configs/common.config", "os:configs/macos.config"]\n')
    parsed = tomllib.loads(board.read_text())
    override = parsed["os_overrides"][PROFILE]
    assert override["payload"]["runtime"]["data_gib"] == 210
    assert override["bootimg"]["max_image_bytes"] == 201326592

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
              "auto_login": True, "hardware_tested": False}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/build-plan.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Prepared pinned full-capacity sources and fresh English automatic-login seed settings.")


if __name__ == "__main__":
    main()
