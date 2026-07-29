export TOP=$(gettop)

apply_patches() {
    cd ${TOP}

    PATCHES_PATH=${TOP}/vendor/patches/patches

    for project_name in $(cd "${PATCHES_PATH}"; echo */); do
        project_path="$(tr _ / <<<$project_name)"
        cd ${TOP}
        cd ${project_path}
        echo "Applying patches for project: ${project_name} on ${HEAD_COMMIT}"
        for patch in "${PATCHES_PATH}"/${project_name}/*.patch; do
            if git apply --reverse --check "${patch}" &> /dev/null; then
                echo "Skipping already applied patch: $(basename "${patch}")"
                continue
            fi

            if ! git am "${patch}" --no-gpg-sign; then
                echo "Failed to apply patch: ${patch}. Aborting."
                git am --abort &> /dev/null
                break
            fi
        done
        cd ${TOP}
    done
}

apply_patches
