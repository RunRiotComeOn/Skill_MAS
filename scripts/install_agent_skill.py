#!/usr/bin/env python3
"""Copy the self-contained Skill-MAS skill into Codex or Claude Code."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import uuid


SKILL_NAME = "skill-mas"
REQUIRED_FILES = (
    "SKILL.md",
    "references/drb.md",
    "references/hlemath.md",
    "references/bcp.md",
    "references/vitabench.md",
)


class InstallError(Exception):
    """A problem that can be explained without a Python traceback."""


def check_path(path, root):
    """Reject symlinks and non-directory ancestors beneath an explicit root."""
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise InstallError("Refusing a symbolic link in installation path: {}".format(current))
        if current.exists() and not current.is_dir():
            raise InstallError("Expected a directory, found another file type: {}".format(current))


def tree_contents(root):
    """Compare exact bytes and directory structure; never follow tree symlinks."""
    def fail_on_walk_error(error):
        raise error

    contents = {}
    for current, directories, files in os.walk(root, followlinks=False, onerror=fail_on_walk_error):
        for name in sorted(directories + files):
            path = Path(current) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise InstallError("Refusing a symbolic link inside a skill: {}".format(path))
            if stat.S_ISDIR(mode):
                contents[path.relative_to(root).as_posix()] = None
            elif stat.S_ISREG(mode):
                contents[path.relative_to(root).as_posix()] = path.read_bytes()
            else:
                raise InstallError("Unsupported file type inside a skill: {}".format(path))
    return contents


def overlaps(left, right):
    return left == right or left in right.parents or right in left.parents


def destinations(args):
    if args.scope == "project":
        root = Path(args.project or Path.cwd()).expanduser().resolve()
        if not root.is_dir():
            raise InstallError("Project directory does not exist: {}".format(root))
    else:
        root = Path.home().resolve()
    selected = ("codex", "claude") if args.agent == "both" else (args.agent,)
    result = []
    for agent in selected:
        base = root / (".agents" if agent == "codex" else ".claude")
        boundary = root
        if agent == "claude" and args.scope == "user" and os.environ.get("CLAUDE_CONFIG_DIR"):
            custom = Path(os.path.abspath(os.path.expanduser(os.environ["CLAUDE_CONFIG_DIR"])))
            # Resolve the explicitly chosen parent, but do not follow the config
            # directory itself if it is a symlink.
            boundary = custom.parent.resolve()
            base = boundary / custom.name
        result.append((agent, base / "skills" / SKILL_NAME, boundary))
    return result


def install(source, targets, force=False, dry_run=False):
    check_path(source, source.parent.parent)
    if not source.is_dir():
        raise InstallError("Skill source is missing: {}. Run this script from a complete repository checkout.".format(source))
    source_contents = tree_contents(source)
    missing = [name for name in REQUIRED_FILES if not source_contents.get(name)]
    if missing:
        raise InstallError("Skill source is incomplete; missing or empty files: {}".format(", ".join(missing)))

    # Inspect every target before creating directories or changing an installation.
    plans = []
    for agent, destination, boundary in targets:
        check_path(destination, boundary)
        if overlaps(source.resolve(), destination.resolve()):
            raise InstallError("Source and destination must not overlap: {}".format(destination))
        for previous in plans:
            if overlaps(previous[1].resolve(), destination.resolve()):
                raise InstallError("Agent installation destinations overlap: {}".format(destination))
        previous_contents = tree_contents(destination) if destination.exists() else None
        backup = None
        if previous_contents is not None and previous_contents != source_contents:
            if not force:
                raise InstallError("Different content already exists at {}. Use --force to back it up and replace it.".format(destination))
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = destination.parent.parent / "skill-backups" / "{}-{}-{}".format(SKILL_NAME, stamp, uuid.uuid4().hex[:8])
            check_path(backup, boundary)
        plans.append((agent, destination, boundary, previous_contents, backup))

    for agent, destination, boundary, previous_contents, backup in plans:
        if previous_contents == source_contents:
            print("Already up to date ({}): {}".format(agent, destination))
            continue
        if dry_run:
            if backup:
                print("Would back up: {} -> {}".format(destination, backup))
            print("Would install ({}): {} -> {}".format(agent, source, destination))
            continue

        check_path(destination, boundary)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".skill-mas-install-", dir=str(destination.parent)) as temporary:
            staged = Path(temporary) / SKILL_NAME
            shutil.copytree(source, staged)
            if tree_contents(staged) != source_contents:
                raise InstallError("Source changed during installation; please retry.")
            check_path(destination, boundary)
            actual = tree_contents(destination) if destination.exists() else None
            if actual != previous_contents:
                raise InstallError("Destination changed during installation; please retry: {}".format(destination))
            if backup:
                check_path(backup, boundary)
                backup.parent.mkdir(parents=True, exist_ok=True)
                # A rename preserves the entire previous installation before
                # the staged copy is promoted. Backups are outside skills/ so
                # agents do not discover them as additional skills.
                destination.rename(backup)
                print("Backed up: {}".format(backup))
            try:
                staged.rename(destination)
            except OSError:
                if backup and not destination.exists():
                    backup.rename(destination)
                    print("Restored previous installation: {}".format(destination), file=sys.stderr)
                raise
        print("Installed ({}): {}".format(agent, destination))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=("codex", "claude", "both"), help="Agent tool(s) to install the skill for")
    parser.add_argument("--scope", choices=("user", "project"), default="user", help="Install for your user (default) or one project")
    parser.add_argument("--project", metavar="PATH", help="Existing project directory; defaults to the current directory (requires --scope project)")
    parser.add_argument("--dry-run", action="store_true", help="Check all destinations and print the planned changes without writing")
    parser.add_argument("--force", action="store_true", help="Back up and replace a differing installation; never replace symlinks")
    args = parser.parse_args(argv)
    if args.project is not None and args.scope != "project":
        parser.error("--project requires --scope project")
    source = Path(__file__).resolve().parent.parent / "skills" / SKILL_NAME
    try:
        install(source, destinations(args), force=args.force, dry_run=args.dry_run)
    except (InstallError, OSError, ValueError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
