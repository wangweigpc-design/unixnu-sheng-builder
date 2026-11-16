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
