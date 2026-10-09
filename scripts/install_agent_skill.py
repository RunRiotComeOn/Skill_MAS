#!/usr/bin/env python3
"""Install Skill-MAS and default background routing in Codex or Claude Code."""

import argparse
from datetime import datetime, timezone
import os
import json
import re
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import uuid


SKILL_NAME = "skill-mas"
REQUIRED_FILES = (
    "SKILL.md",
    "references/default-routing.md",
    "references/drb.md",
    "references/hlemath.md",
    "references/bcp.md",
    "references/vitabench.md",
)

BEGIN = b"<!-- SKILL-MAS:BEGIN -->"
END = b"<!-- SKILL-MAS:END -->"


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


def instruction_contents(path, boundary):
    """Read an instruction file without following a symlink or special file."""
    check_path(path.parent, boundary)
    if path.is_symlink():
        raise InstallError("Refusing a symbolic link in instruction path: {}".format(path))
    if path.exists() and not path.is_file():
        raise InstallError("Expected a regular instruction file: {}".format(path))
    return path.read_bytes() if path.exists() else None


def managed_span(contents, path):
    """Validate and find the complete owned block, including its final newline."""
    contents = contents or b""
    if b"<!-- SKILL-MAS:" not in contents:
        return None
    if (contents.count(BEGIN) != 1 or contents.count(END) != 1
            or contents.count(b"<!-- SKILL-MAS:") != 2):
        raise InstallError("Malformed or duplicate Skill-MAS markers in {}".format(path))
    match = re.search(rb"(?ms)^" + re.escape(BEGIN) + rb"\r?\n.*?^"
                      + re.escape(END) + rb"(?:\r?\n|\Z)", contents)
    if not match:
        raise InstallError("Malformed or unpaired Skill-MAS markers in {}".format(path))
    return match.span()


def merge_block(contents, span, block):
    contents = contents or b""
    if span:
        return contents[:span[0]] + block + contents[span[1]:]
    # Prepending makes even a file without a trailing newline round-trip exactly.
    return block + contents


def plan_routing(source, source_contents, targets, args):
    """Preflight every instruction destination before any skill is written."""
    policy = source_contents["references/default-routing.md"].decode("utf-8").strip()
    if not policy or "<!-- SKILL-MAS:" in policy:
        raise InstallError("Default routing source is empty or contains reserved Skill-MAS markers.")
    project = Path(args.project or Path.cwd()).expanduser().resolve()
    plans = []
    for agent, skill, skill_boundary in targets:
        if args.scope == "project":
            config = project / (".agents" if agent == "codex" else ".claude")
            boundary = project
            backup_root = config / "skill-backups"
            entry = skill.relative_to(project).as_posix() + "/SKILL.md"
            path_kind = "project-relative"
        else:
            boundary = skill_boundary
            config = skill.parent.parent
            if agent == "codex":
                custom = Path(os.path.abspath(os.path.expanduser(
                    os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))))
                boundary = custom.parent.resolve()
                config = boundary / custom.name
            backup_root = config / "skill-backups"
            entry = str(skill / "SKILL.md")
            path_kind = "absolute"

        body = (policy + "\n\nInstalled Skill-MAS entry point (JSON-encoded "
                + path_kind + " path; read this SKILL.md when routing applies):\n\n    "
                + json.dumps(entry, ensure_ascii=True) + "\n").encode("utf-8")
        block = BEGIN + b"\n" + body + END + b"\n"
        if agent == "codex":
            instruction_root = project if args.scope == "project" else config
            candidates = [instruction_root / "AGENTS.md", instruction_root / "AGENTS.override.md"]
            existing = [instruction_contents(path, boundary) for path in candidates]
            # Codex gives a nonempty override precedence. Do not create one.
            active = 1 if existing[1] and existing[1].strip() else 0
        else:
            candidates = [config / "rules" / (SKILL_NAME + ".md")]
            existing = [instruction_contents(candidates[0], boundary)]
            active = 0

        for index, (path, previous) in enumerate(zip(candidates, existing)):
            if overlaps(source.resolve(), path.resolve()):
                raise InstallError("Instruction path and source overlap: {}".format(path))
            for _, destination, _ in targets:
                if overlaps(destination.resolve(), path.resolve()):
                    raise InstallError("Instruction path and skill destination overlap: {}".format(path))
            if any(overlaps(plan["path"].resolve(), path.resolve()) for plan in plans):
                raise InstallError("Agent instruction destinations overlap: {}".format(path))
            span = managed_span(previous, path)
            enabled = not args.no_default_routing and index == active
            if agent == "claude" and enabled:
                owned = span is not None and not merge_block(previous, span, b"").strip()
                if previous is not None and not owned and not args.force:
                    raise InstallError("Unmanaged instruction file already exists at {}. Use --force to back it up and replace it.".format(path))
                updated = block
            elif enabled:
                updated = merge_block(previous, span, block)
            elif span:
                updated = merge_block(previous, span, b"")
                # Keep a preexisting Codex file, including an empty override.
                if agent == "claude" and not updated.strip():
                    updated = None
            else:
                updated = previous

            backup = None
            if previous is not None and previous != updated:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = backup_root / "{}-{}-{}-{}".format(agent, path.name, stamp, uuid.uuid4().hex[:8])
                check_path(backup.parent, boundary)
                if backup.exists() or backup.is_symlink():
                    raise InstallError("Backup path already exists: {}".format(backup))
            plans.append({"agent": agent, "path": path, "boundary": boundary,
                          "previous": previous, "updated": updated, "backup": backup,
                          "block": block if enabled else None,
                          "mode": stat.S_IMODE(path.stat().st_mode) if previous is not None else 0o644})
    return plans


def apply_routing(plans, dry_run=False):
    for plan in plans:
        path, boundary = plan["path"], plan["boundary"]
        previous, updated, backup = plan["previous"], plan["updated"], plan["backup"]
        if previous == updated:
            if updated is not None:
                print("Routing already up to date: {}".format(path))
            continue
        action = "write" if plan["block"] is not None else "remove"
        if dry_run:
            if backup:
                print("Would back up: {} -> {}".format(path, backup))
            print("Would {} default routing ({}): {}".format(action, plan["agent"], path))
            if plan["block"] is not None:
                print(plan["block"].decode("utf-8"))
            continue
        if instruction_contents(path, boundary) != previous:
            raise InstallError("Instruction file changed during installation; please retry: {}".format(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup:
            check_path(backup.parent, boundary)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            print("Backed up: {}".format(backup))
        if updated is None:
            path.unlink()
        else:
            descriptor, temporary = tempfile.mkstemp(prefix=".skill-mas-routing-", dir=str(path.parent))
            try:
                with os.fdopen(descriptor, "wb") as staged:
                    staged.write(updated)
                os.chmod(temporary, plan["mode"])
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        print("Default routing {} ({}): {}".format("updated" if plan["block"] is not None else "removed", plan["agent"], path))


def install(source, targets, args, force=False, dry_run=False):
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

    routing_plans = plan_routing(source, source_contents, targets, args)

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

    apply_routing(routing_plans, dry_run=dry_run)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=("codex", "claude", "both"), help="Agent tool(s) to install the skill for")
    parser.add_argument("--scope", choices=("user", "project"), default="user", help="Install for your user (default) or one project")
    parser.add_argument("--project", metavar="PATH", help="Existing project directory; defaults to the current directory (requires --scope project)")
    parser.add_argument("--dry-run", action="store_true", help="Check all destinations and print the planned changes without writing")
    parser.add_argument("--no-default-routing", action="store_true", help="Install the skill without background routing; remove prior managed routing and retain normal host skill discovery")
    parser.add_argument("--force", action="store_true", help="Back up and replace differing skills or unmanaged routing files; never replace symlinks")
    args = parser.parse_args(argv)
    if args.project is not None and args.scope != "project":
        parser.error("--project requires --scope project")
    source = Path(__file__).resolve().parent.parent / "skills" / SKILL_NAME
    try:
        install(source, destinations(args), args, force=args.force, dry_run=args.dry_run)
    except (InstallError, OSError, ValueError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
