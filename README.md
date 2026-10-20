# Vendor patches

Place this repo at `<ROM>/vendor/patches`. Requires Python 3.8+ and Git.
The source project must already exist, and your changes must be committed.

## Update a project's patches

Run from `vendor/patches`:

```bash
cd /path/to/rom/vendor/patches
```

Show the commits you want to export:

```bash
git -C ../../frameworks/base log --oneline --no-decorate
```

Start the script:

```bash
./update_patches.py frameworks/base --write
```

Paste **all commits you want to keep**, newest to oldest. Hashes alone or
complete one-line log entries both work. Press **Enter on a blank line** when
finished.

The script creates `patches/frameworks_base/` and numbers patches oldest first
(`0001`, `0002`, ...). It backs up the old folder in `patch-backups/` and replaces
the whole project's series. You do not need to delete old patches first.
Exporting patches does not change commits in your source repo.

For other projects, use their full source paths:

```bash
./update_patches.py frameworks/av --write
./update_patches.py device/axion/common --write
./update_patches.py packages/apps/Settings --write
```

New patch folders are created automatically. For example,
`packages/apps/Settings` becomes `patches/packages_apps_Settings/`.

Omit `--write` to preview only. Use `--oldest-first` if your input list is oldest
first, or `--commits FILE` to read a saved list. Show all options with:

```bash
./update_patches.py --help
```

## Add or replace one patch

From `vendor/patches`, export a local commit (replace `COMMIT_HASH`):

```bash
./create_patch.py frameworks/base COMMIT_HASH --repo ../../frameworks/base
```

This adds the next numbered patch. To overwrite one existing patch, add
`--replace` with its exact filename:

```bash
./create_patch.py frameworks/base COMMIT_HASH --repo ../../frameworks/base --replace 0001-existing-patch.patch
```

Single-file replacement keeps its filename and does not create a backup.
You can also download a GitHub commit using its URL:

```bash
./create_patch.py packages/apps/Settings https://github.com/OWNER/REPO/commit/COMMIT_HASH
```

## Apply patches and handle failures

From the **ROM source root**, load the build environment:

```bash
source build/envsetup.sh
```

Vendor setup applies patches automatically when enabled. If a patch fails,
it stops and prints the project, patch filename, and error. Normal Make/Kati
ROM builds are blocked until setup succeeds; direct Soong-only commands bypass
this gate.

After fixing the problem, rerun in the same shell from the ROM root:

```bash
source vendor/patches/vendorsetup.sh
```

## Save your changes

From `vendor/patches`, review and commit the updated patch files:

```bash
git status --short
git diff -- patches/
git add patches/
git diff --cached --stat
git commit -m "patches: update patch series"
```
