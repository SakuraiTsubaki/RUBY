#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

UPSTREAM = "https://github.com/pret/pokeruby.git"
REF = "63a8cbf0016b351a4e68f7036fa0b77e23d2f2c1"

ROOT = Path(__file__).resolve().parents[1]
PATCHES = [
    ROOT / "patches" / "pokeruby" / "gen10-rom-capacity.patch",
    ROOT / "patches" / "pokeruby" / "gen10-save-extension.patch",
    ROOT / "patches" / "pokeruby" / "gen10-mon-metadata-movement.patch",
    ROOT / "patches" / "pokeruby" / "gen10-save-migration.patch",
    ROOT / "patches" / "pokeruby" / "gen10-ability-id-api.patch",
    ROOT / "patches" / "pokeruby" / "gen10-id-types.patch",
]


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare the ROM/save-grounded RUBY Generation X foundation.")
    ap.add_argument("target", nargs="?", type=Path, default=ROOT / "build" / "pokeruby-gen10")
    args = ap.parse_args()
    target = args.target.resolve()

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", UPSTREAM, str(target))

    if not (target / ".git").exists():
        print(f"target is not a git worktree: {target}", file=sys.stderr)
        return 2

    run("git", "fetch", "--all", "--tags", cwd=target)
    run("git", "checkout", "--detach", REF, cwd=target)
    run("git", "reset", "--hard", REF, cwd=target)
    run("git", "clean", "-fdx", cwd=target)

    for patch in PATCHES:
        if not patch.is_file():
            print(f"missing patch: {patch}", file=sys.stderr)
            return 2
        run("git", "apply", "--check", str(patch), cwd=target)
        run("git", "apply", str(patch), cwd=target)

    run("git", "diff", "--check", cwd=target)
    print()
    print("Generation X RUBY foundation prepared.")
    print(f"Source: {UPSTREAM}@{REF}")
    print("Capacity build command:")
    print(f"  make -C {target} ROM_END=0xA000000")
    print("No ROM or save binary is copied into the RUBY repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
