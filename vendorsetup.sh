export TOP=$(gettop)

apply_patches() {
    cd ${TOP}

    PATCHES_PATH=${TOP}/vendor/patches/patches

    for project_name in $(cd "${PATCHES_PATH}"; echo */); do
        project_path="$(tr _ / <<<$project_name)"
        cd ${TOP}
        cd ${project_path}
        echo "Applying patches for project: ${project_name} on ${HEAD_COMMIT}"
        if ! git am "${PATCHES_PATH}"/${project_name}/*.patch --no-gpg-sign; then
            echo "Failed to apply patches for project: ${project_name}. Aborting."
            git am --abort &> /dev/null
        fi
        cd ${TOP}
    done
}

apply_patches
