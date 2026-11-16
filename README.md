# UniXNU sheng build runner

This standalone publication folder contains only build automation for the public
UniXNU Xiaomi Pad 6S Pro sources. It is not a copy of the private installation
project, device backups, credentials, or NAS configuration.

## Runner check

The manually dispatched `Check standard macOS runner` workflow checks a standard
`macos-26` GitHub-hosted runner. It has a five-minute limit, read-only repository
permissions, and no artifact upload or cache steps. It prints host/tool versions
and checks Xcode, `hdiutil`, and `diskutil` availability.

GitHub documents standard hosted runners for public repositories as free of
compute charges: https://docs.github.com/en/billing/concepts/product-billing/github-actions

This does not establish that the account is eligible to start a job. An
account-level billing or Actions restriction may still prevent scheduling. The
runner check must succeed before an image build is attempted.

No personal installation data or account secrets are required for this check.
There are no push, pull-request, or scheduled triggers.

## Upstream

- https://github.com/UniXNU/UniXNU
- https://github.com/UniXNU/UniXNU-sheng
- https://github.com/UniXNU/uefi-sheng

An image build and its hardware qualification are separate from this environment
check. Passing this workflow does not produce a flashable image.

## Full-capacity build

`Build encrypted full-capacity macOS images` follows the pinned upstream macOS
lab sources for profile `macos-27.3-26C5035r`. It creates a fresh 210 GiB Data
seed, uses the stock `userdata` layout, limits boot images to 192 MiB, and
configures English initial preferences and automatic login. The installer parser
shadowing error is repaired with an exact source check. It does not flash a device.

Required repository secrets are `UNIXNU_UNIQUE_CHIP_ID` and
`MACOS_TEMP_PASSWORD`. `ARTIFACT_AGE_RECIPIENT` is a public age recipient stored
as a repository variable. The corresponding private decryption identity stays
outside GitHub. Private installation inputs, images, policy keys, and diagnostic
bundles are encrypted before they are uploaded as release assets. No Actions
artifact or cache uploads are configured.

The workflow uses a standard runner, two compilation jobs, and a six-hour job
limit. Build success does not imply hardware stability or verified charging,
sleep, video, or graphics behavior. Check the upstream device evidence and test
the resulting image on the intended tablet before calling it qualified.
