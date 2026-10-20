#!/usr/bin/env python3
"""Refresh a complete project patch series from a pasted git log commit list."""

import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from create_patch import git


ROOT = Path(__file__).resolve().parent


def prepare(repo, lines, oldest_first=False):
    commits = []
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split()[0]
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", token):
            raise ValueError(f"line {number}: expected a commit hash followed by an optional subject")
        commit = git(repo, "rev-parse", "--verify", "--end-of-options", token + "^{commit}").decode().strip()
        if commit in commits:
            raise ValueError(f"line {number}: duplicate commit {token}")
        commits.append(commit)
    if not commits:
        raise ValueError("the commit list is empty")
    if not oldest_first:
        commits.reverse()
    if len(commits) > 9999:
        raise ValueError("at most 9999 patches are supported")

    patches = []
    previous = None
    for number, commit in enumerate(commits, 1):
        if previous:
            result = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", previous, commit],
                capture_output=True,
            )
            if result.returncode:
                raise ValueError("commits must follow one ancestry chain, newest first (or use --oldest-first)")
        previous = commit
        if len(git(repo, "rev-list", "--parents", "-n", "1", commit).split()) > 2:
            raise ValueError(f"cannot export merge commit {commit[:12]}")
        data = git(repo, "format-patch", "--stdout", "--no-signature", "--no-cover-letter",
                   "--no-stat", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
                   "--root", "-1", commit)
        if len(re.findall(rb"^From [0-9a-f]{40,64} Mon Sep 17 00:00:00 2001\r?$", data, re.M)) != 1 or not re.search(rb"^diff --git ", data, re.M):
            raise ValueError(f"commit {commit[:12]} did not produce one nonempty patch")
        title = git(repo, "show", "-s", "--format=%s", commit).decode(errors="replace").strip()
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip(".-")[:100] or "commit"
        patches.append((f"{number:04d}-{slug}.patch", data))
    return patches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Android project, e.g. frameworks/base")
    parser.add_argument("--commits", type=Path, help="text file of hashes, newest first; omit to paste a list")
    parser.add_argument("--repo", type=Path, help="override the automatically located source project")
    parser.add_argument("--oldest-first", action="store_true", help="input list is already oldest first")
    parser.add_argument("--write", action="store_true", help="back up and replace the complete project series; otherwise preview only")
    args = parser.parse_args()
    project = args.project
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", project) or any(
        part in (".", "..") for part in project.split("/")
    ):
        parser.error("project must be a relative Android project path")
    if args.repo:
        repo = args.repo.resolve()
    else:
        # Installed at <ROM>/vendor/patches/update_patches.py.
        if ROOT.name != "patches" or ROOT.parent.name != "vendor":
            parser.error("outside <ROM>/vendor/patches, specify --repo /path/to/project")
        repo = ROOT.parent.parent / project
    if not repo.is_dir() or Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo.resolve():
        parser.error(f"source must be a Git project root: {repo}")
    folder = ROOT / "patches" / project.replace("/", "_")
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        parser.error(f"expected a regular project folder: {folder}")
    if folder.exists() and any(not path.is_file() or path.is_symlink() or path.suffix != ".patch" for path in folder.iterdir()):
        parser.error(f"project folder contains files other than regular .patch files: {folder}")

    if args.commits:
        lines = args.commits.read_text().splitlines()
    elif sys.stdin.isatty():
        print("Paste commits newest first (git log lines work). Finish with a blank line:")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip():
                break
            lines.append(line)
    else:
        lines = sys.stdin.read().splitlines()

    patches = prepare(repo, lines, args.oldest_first)
    old_count = len(list(folder.glob("*.patch")))
    print(f"Source: {repo}")
    print(f"Replace all {old_count} existing patches in {folder} with {len(patches)} patches:")
    for name, _ in patches:
        print(f"  {name}")
    if not args.write:
        print("Preview only. Run again with --write to save this series with a backup.")
        return

    folder.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".patch-series-", dir=folder.parent) as staging:
        staged = Path(staging) / folder.name
        staged.mkdir()
        for name, data in patches:
            (staged / name).write_bytes(data)
        if folder.exists():
            backups = ROOT / "patch-backups"
            backups.mkdir(exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix=folder.name + "-", dir=backups)) / folder.name
            folder.rename(backup)
        try:
            staged.rename(folder)
        except OSError:
            if backup is not None:
                backup.rename(folder)
            raise
    print(f"Saved {len(patches)} patches.")
    if backup is not None:
        print(f"Previous series backed up at: {backup}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
