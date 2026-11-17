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

The selected macOS archive plan uses the matching macOS signed-root policies.
SoftwareAES is built by the board's Darwin 26 ABI adapter, not its generic iPadOS
component recipe. The plan is checked before runtime compilation. Three static
UEFI memory ranges are narrowed for the older-firmware 12 GiB layout; the upstream
8 GiB live-map guard is preserved. A verified original DTB is still needed during
private final packaging for that older bootloader. The logical payload FAT is
256 MiB and is chunk-compressed; the physical Android boot limit remains 192 MiB.

The pinned device snapshot has a truncated `SourceStorage.cpp`. Its missing
startup tail is recovered from complete revision
`d7c7aee91fe740f5b986165312aa7044cd09dfd4`, with both input hashes checked.
Root-policy authentication, storage-family/APFS loading, class registration,
UFS startup and Data startup remain intact. Current timing conversions are
preserved; optional startup checkpoints are connected to the restored function.
The storage porting record records this repair and its pending hardware status.

Required repository secrets are `UNIXNU_UNIQUE_CHIP_ID` and
`MACOS_TEMP_PASSWORD`. `ARTIFACT_AGE_RECIPIENT` is a public age recipient stored
as a repository variable. The corresponding private decryption identity stays
outside GitHub. Private installation inputs, images, policy keys, and diagnostic
bundles are encrypted before they are uploaded as release assets. No Actions
artifact or cache uploads are configured.

On failure, completed Data/runtime inputs are retained in the encrypted bundle
with their checksums, so later repairs can reuse them after validation.
An optional runtime-only cache uses `RUNTIME_CACHE_RELEASE` and
`RUNTIME_CACHE_SHA256` repository variables and a separate
`RUNTIME_CACHE_AGE_IDENTITY` secret. The installer-image decryption identity is
never reused for this cache. Restoring checks the source pins, profile, seed
capacity, filenames, sizes and hashes before the original builder consumes the
inputs. Kernel compilation, signed-root generation and output checks still run.

The RELEASE reference build also honours `JOBS` instead of its upstream
hard-coded eight workers. If compilation stops before the link file list exists,
its compiler errors are printed and all nested build logs are retained in the
encrypted diagnostics.
The macOS outside-memory probe needs Apple's `add_saved_state_pc` helper. The
RELEASE comparison copy enables that original helper with a scoped feature
guard; its signed-thread-state checks remain unchanged. The booted DEVELOPMENT
kernel is not modified by this comparison-only repair.
Its existing optional-hook stubs include the newer weak board logging hooks;
the final booted kernel continues to use the actual board implementations.
The comparison kernel also follows `UNIXNU_XNU_TARGET`, just like the main
kernel: macOS selects `XNU_TARGET_OS_OSX` and its padded IOKit vtables. The
original iOS object platform is retained. The selected target participates in
the comparison cache identity, and unsupported targets are rejected.

Compiler source paths are normalized from the CI workspace to `/src` using
`-ffile-prefix-map`. This reduces embedded path strings in the fixed-size native
`__TEXT` placement without removing drivers or relaxing layout checks. An early
Apple-clang probe checks that its path string shortens while its instructions
stay identical. The full kernel still has to pass the normal prelink checks.
Failed builds retain completed native/kernelcache inputs in the encrypted
diagnostics so layout issues can be reproduced offline.

The workflow uses a standard runner, two compilation jobs, and a six-hour job
limit. Build success does not imply hardware stability or verified charging,
sleep, video, or graphics behavior. Check the upstream device evidence and test
the resulting image on the intended tablet before calling it qualified.
