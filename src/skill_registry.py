from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from retrieve_chroma_docs import retrieve_stylus_context

SKILL_ID_RESEARCH = "sift-stylus-research"
SKILL_ID_PORTING_AUDITOR = "sift-stylus-porting-auditor"


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    label: str
    description: str
    search_handler: Callable[[str], dict]


def _run_shared_retrieval(prompt: str) -> dict:
    return retrieve_stylus_context(prompt)


SKILL_REGISTRY: Dict[str, SkillDefinition] = {
    SKILL_ID_RESEARCH: SkillDefinition(
        skill_id=SKILL_ID_RESEARCH,
        label="Stylus Research",
        description="References-first research for Arbitrum Stylus tooling and ecosystem questions.",
        search_handler=_run_shared_retrieval,
    ),
    SKILL_ID_PORTING_AUDITOR: SkillDefinition(
        skill_id=SKILL_ID_PORTING_AUDITOR,
        label="Porting Auditor",
        description=(
            "Impact-focused candidacy checks for hybrid Solidity and Stylus architectures."
        ),
        search_handler=_run_shared_retrieval,
    ),
}


def get_skill(skill_id: str) -> Optional[SkillDefinition]:
    return SKILL_REGISTRY.get(skill_id)


def list_skills() -> List[dict]:
    return [
        {
            "id": item.skill_id,
            "label": item.label,
            "description": item.description,
            "search_path": f"/skills/{item.skill_id}/search",
        }
        for item in SKILL_REGISTRY.values()
    ]


def run_skill_search(skill_id: str, prompt: str) -> dict:
    skill = get_skill(skill_id)
    if skill is None:
        raise KeyError(skill_id)

    payload = skill.search_handler(prompt)
    if isinstance(payload, dict):
        payload.setdefault("skill", skill_id)
    return payload
