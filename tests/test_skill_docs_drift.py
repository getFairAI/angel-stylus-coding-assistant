"""Guard against drift between skill documentation and the live skill registry.

The published SKILL.md / reference docs advertise backend endpoints and the MCP
tool names that consumers wire against. If a documented `/skills/<id>/search`
path names an id that is not registered, real integrations 404. These tests keep
the docs and `skill_registry.SKILL_REGISTRY` in lock-step.
"""

import re
from pathlib import Path

import pytest

from skill_registry import SKILL_REGISTRY

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

SEARCH_PATH_RE = re.compile(r"/skills/([A-Za-z0-9_-]+)/search")
# The one canonical name for the code-retrieval MCP tool.
CANONICAL_CODE_TOOL = "search_stylus_code"
DEPRECATED_CODE_TOOL = "stylus_search_code"


def _skill_markdown_files() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("*.md"))


def test_skills_dir_present():
    assert SKILLS_DIR.is_dir(), f"expected skills dir at {SKILLS_DIR}"
    assert _skill_markdown_files(), "no skill markdown files found"


@pytest.mark.parametrize("doc", _skill_markdown_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_documented_search_paths_are_registered(doc: Path):
    """Every `/skills/<id>/search` referenced in docs must be a registered skill id."""
    registered = set(SKILL_REGISTRY.keys())
    text = doc.read_text(encoding="utf-8")
    for skill_id in SEARCH_PATH_RE.findall(text):
        assert skill_id in registered, (
            f"{doc.relative_to(REPO_ROOT)} documents endpoint /skills/{skill_id}/search "
            f"but no such skill is registered. Registered ids: {sorted(registered)}"
        )


def test_no_deprecated_code_tool_name():
    """The code-retrieval tool must be named consistently across all skill docs."""
    offenders = [
        str(doc.relative_to(REPO_ROOT))
        for doc in _skill_markdown_files()
        if DEPRECATED_CODE_TOOL in doc.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"deprecated tool name `{DEPRECATED_CODE_TOOL}` still present in {offenders}; "
        f"use `{CANONICAL_CODE_TOOL}`"
    )
