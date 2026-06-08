import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import GITHUB_ANALYZE_PROMPT
from app.services.github_client import GitHubClient
from app.services.llm import get_llm


class GitHubAnalysisService:
    async def analyze(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        github_username: str,
        target_company: str,
        target_role: str,
        github_token: str | None = None,
    ) -> dict[str, Any]:
        if not github_username:
            return {"error": "No GitHub username provided"}

        client = GitHubClient(access_token=github_token)
        github_data = await client.analyze_profile(github_username)

        llm = get_llm()
        target = f"{target_company} {target_role}"
        response = await llm.ainvoke(
            [
                SystemMessage(content=GITHUB_ANALYZE_PROMPT),
                HumanMessage(
                    content=f"Target role: {target}\n\nGitHub data:\n{json.dumps(github_data, indent=2)[:8000]}"
                ),
            ]
        )
        github_data["analysis"] = response.content
        return github_data
