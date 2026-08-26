"""Record the actual execution environment.

Framework versions are never hand-written into the paper: a version typed into
a methods section is a claim that has not been verified. This script reads the
installed distributions and writes the truth to
experiments/configs/environment.json, from which the Section 3.5 table is
generated.
"""

from __future__ import annotations

import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, distributions, version
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "experiments" / "configs" / "environment.json"

TRACKED = [
    "langgraph", "langchain-core", "crewai", "autogen-agentchat", "pyautogen",
    "anthropic", "pandas", "numpy", "scipy", "psutil", "jsonschema", "pyyaml",
]


def resolved(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main() -> None:
    record = {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "build": " ".join(platform.python_build()),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "tracked_packages": {name: resolved(name) for name in TRACKED},
        "all_packages": {
            dist.metadata["Name"]: dist.version
            for dist in distributions()
            if dist.metadata.get("Name")
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    missing = [n for n, v in record["tracked_packages"].items() if v is None]
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    if missing:
        print("NOT INSTALLED (config.yaml must stay PENDING_INSTALL for these): "
              + ", ".join(missing))


if __name__ == "__main__":
    main()
