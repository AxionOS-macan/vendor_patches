#!/usr/bin/env python3
"""Download or export a commit into this repository's patch collection."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


PATCHES = Path(__file__).resolve().parent / "patches"


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Android project path, e.g. frameworks/base")
    parser.add_argument("source", nargs="?", default="HEAD", help="commit URL or local commit (default: HEAD)")
    parser.add_argument("--repo", type=Path, help="local Git project to export from")
    parser.add_argument("--replace", metavar="FILENAME", help="replace this existing patch in the project folder, keeping its name/order")
    args = parser.parse_args()

    project = args.project.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", project) or any(
        part in (".", "..") for part in project.split("/")
    ):
        parser.error("project must be a relative Android project path")
    folder = PATCHES / project.replace("/", "_")
    target = None
    if args.replace:
        if Path(args.replace).name != args.replace or not args.replace.endswith(".patch"):
            parser.error("--replace requires a .patch filename without directories")
        target = folder / args.replace
        if not target.is_file() or target.is_symlink():
            parser.error(f"existing regular patch required: {target}")

    if args.source.startswith(("http://", "https://")):
        if args.repo:
            parser.error("use either a URL or --repo")
        url = urlsplit(args.source)
        if url.scheme != "https":
            parser.error("use an HTTPS commit or patch URL")
        path = url.path.rstrip("/")
        if url.hostname == "github.com" and re.fullmatch(r"/[^/]+/[^/]+/commit/[0-9a-fA-F]+", path):
            path += ".patch"
        source = urlunsplit((url.scheme, url.netloc, path, url.query, ""))
        request = Request(source, headers={"User-Agent": "vendor-patches-helper"})
        with urlopen(request, timeout=60) as response:
            data = response.read()
    else:
        if args.repo is None:
            parser.error("local commits require --repo /path/to/project")
        commit = git(args.repo, "rev-parse", "--verify", "--end-of-options", args.source + "^{commit}").decode().strip()
        parents = git(args.repo, "rev-list", "--parents", "-n", "1", commit).split()
        if len(parents) > 2:
            parser.error("merge commits cannot be exported as a single ordinary patch; select a non-merge commit")
        data = git(args.repo, "format-patch", "--stdout", "--no-signature", "--no-cover-letter", "--no-stat", "--binary", "--full-index", "--no-ext-diff", "--no-textconv", "--root", "-1", commit)

    # vendorsetup.sh uses git am, so reject HTML, raw diffs, and multi-commit downloads.
    commits = re.findall(rb"^From ([0-9a-f]{40,64}) Mon Sep 17 00:00:00 2001\r?$", data, re.M)
    subject = re.search(rb"^Subject: (.*(?:\r?\n[ \t].*)*)", data, re.M)
    if len(commits) != 1 or not subject or not re.search(rb"^diff --git ", data, re.M):
        raise ValueError("expected one nonempty git format-patch email; check the URL or commit")

    existing = sorted(folder.glob("*.patch"))
    for patch in existing:
        if patch == target:
            continue
        content = patch.read_bytes()
        if content == data or re.search(rb"^From " + commits[0] + rb" Mon Sep 17", content, re.M):
            raise ValueError(f"commit already saved as {patch}")

    if target is None:
        numbers = [int(match.group(1)) for patch in existing
                   if (match := re.match(r"^(\d+)-", patch.name))]
        number = max(numbers, default=0) + 1
        if number > 9999:
            raise ValueError("four-digit patch numbering exhausted")
        title = re.sub(r"\s+", " ", subject.group(1).decode(errors="replace"))
        title = re.sub(r"^\[PATCH[^]]*\]\s*", "", title)
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip(".-")[:100] or "commit"
        target = folder / f"{number:04d}-{slug}.patch"

    folder.mkdir(parents=True, exist_ok=True)
    if args.replace:
        # Write fully before replacing the old patch, so failed writes preserve it.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                os.fchmod(stream.fileno(), target.stat().st_mode & 0o777)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    else:
        with target.open("xb") as stream:
            stream.write(data)
    print(f"{'Updated' if args.replace else 'Created'}: {target}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
