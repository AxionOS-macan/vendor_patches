#!/bin/bash

# Run in a subshell so sourcing this file preserves the caller's directory/options.
apply_patches() (
    set -o pipefail
    local top patches_path status_file project_dir project_path patch
    local patch_id history_ids history_loaded applied=0 skipped=0

    top=$(gettop) || return 1
    if [ -z "$top" ]; then
        echo "ERROR: Cannot locate the ROM source root." >&2
        return 1
    fi
    patches_path="$top/vendor/patches/patches"
    status_file="$top/vendor/patches/.patches-failed"

    patch_failure() {
        printf 'Project: %s\nPatch: %s\nReason: %s\n' \
            "${project_path:-unknown}" "${patch:-not selected}" "$1" > "$status_file"
        printf '\nERROR: Vendor patches failed; ROM build is blocked.\n' >&2
        cat "$status_file" >&2
        echo "Fix the problem, then rerun: source vendor/patches/vendorsetup.sh" >&2
        return 1
    }

    # Leave a failure marker even if setup is interrupted before completion.
    printf 'Vendor patch setup has not completed. Rerun source vendor/patches/vendorsetup.sh\n' > "$status_file" || return 1
    if [ ! -d "$patches_path" ]; then
        patch_failure "Patch collection is missing: $patches_path"
        return 1
    fi

    for project_dir in "$patches_path"/*/; do
        [ -d "$project_dir" ] || continue
        project_path=${project_dir%/}
        project_path=${project_path##*/}
        project_path=${project_path//_/\/}
        history_loaded=0
        history_ids=
        for patch in "$project_dir"*.patch; do
            [ -e "$patch" ] || continue
            printf 'Project: %s\nPatch: %s\nReason: Setup interrupted while processing this patch\n' \
                "$project_path" "$patch" > "$status_file" || return 1
            if [ ! -d "$top/$project_path" ] || ! cd "$top/$project_path"; then
                patch_failure "Source project directory is missing"
                return 1
            fi
            if [ "$(git rev-parse --show-toplevel 2>/dev/null)" != "$(pwd -P)" ]; then
                patch_failure "Source directory is not a Git project root"
                return 1
            fi
            if [ -d "$(git rev-parse --git-path rebase-apply)" ] || [ -d "$(git rev-parse --git-path rebase-merge)" ]; then
                patch_failure "An existing git am/rebase is in progress; resolve it first"
                return 1
            fi
            if ! git apply --numstat "$patch" >/dev/null; then
                patch_failure "Invalid or empty patch file"
                return 1
            fi
            if git apply --reverse --check "$patch" >/dev/null 2>&1; then
                echo "Already applied: $project_path/$(basename "$patch")"
                skipped=$((skipped + 1))
                continue
            fi

            # Later commits may change an earlier patch's lines. Compare actual
            # diffs with recent history instead of trusting matching subjects.
            if [ "$history_loaded" -eq 0 ]; then
                if ! history_ids=$(git log -n 500 --no-merges --format=medium -p --binary --no-ext-diff --no-textconv | git patch-id --stable); then
                    patch_failure "Cannot inspect Git history for applied patches"
                    return 1
                fi
                history_loaded=1
            fi
            if ! patch_id=$(git patch-id --stable < "$patch"); then
                patch_failure "Cannot read patch ID"
                return 1
            fi
            patch_id=${patch_id%% *}
            if [ -z "$patch_id" ]; then
                patch_failure "Patch contains no changes"
                return 1
            fi
            if printf '%s\n' "$history_ids" | awk -v id="$patch_id" '$1 == id { found=1 } END { exit !found }'; then
                echo "Already applied (matching patch ID): $project_path/$(basename "$patch")"
                skipped=$((skipped + 1))
                continue
            fi
            if ! git diff --quiet || ! git diff --cached --quiet; then
                patch_failure "Uncommitted tracked changes; commit or stash them before applying patches"
                return 1
            fi
            echo "Applying: $project_path/$(basename "$patch")"
            if ! git am --no-gpg-sign "$patch"; then
                if [ -d "$(git rev-parse --git-path rebase-apply)" ]; then
                    if ! git am --abort; then
                        echo "ERROR: git am --abort also failed; inspect the project manually." >&2
                    fi
                fi
                patch_failure "git am failed; see Git's error above"
                return 1
            fi
            applied=$((applied + 1))
            # Refresh history if a subsequent patch needs a history check.
            history_loaded=0
        done
    done
    rm -f "$status_file" || return 1
    echo "Vendor patches ready: $applied applied, $skipped already applied."
)

apply_patches
