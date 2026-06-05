from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token
        self._cache: dict[str, tuple[datetime, dict]] = {}
        self._cache_ttl = timedelta(hours=1)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _get_cached(self, key: str) -> dict | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if datetime.now(timezone.utc) - ts < self._cache_ttl:
                return data
        return None

    def _set_cache(self, key: str, data: dict) -> None:
        self._cache[key] = (datetime.now(timezone.utc), data)

    async def get_user(self, username: str) -> dict[str, Any]:
        cache_key = f"user:{username}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{GITHUB_API}/users/{username}", headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            self._set_cache(cache_key, data)
            return data

    async def get_repos(self, username: str, max_repos: int = 30) -> list[dict[str, Any]]:
        cache_key = f"repos:{username}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GITHUB_API}/users/{username}/repos",
                headers=self._headers(),
                params={"sort": "updated", "per_page": max_repos},
            )
            resp.raise_for_status()
            data = resp.json()
            self._set_cache(cache_key, data)
            return data

    async def analyze_profile(self, username: str) -> dict[str, Any]:
        user = await self.get_user(username)
        repos = await self.get_repos(username)

        languages: dict[str, int] = {}
        for repo in repos:
            lang = repo.get("language")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1

        starred = sum(r.get("stargazers_count", 0) for r in repos)
        with_readme = sum(1 for r in repos if r.get("description"))

        top_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:10]

        return {
            "username": username,
            "name": user.get("name"),
            "bio": user.get("bio"),
            "public_repos": user.get("public_repos", 0),
            "followers": user.get("followers", 0),
            "languages": languages,
            "total_stars": starred,
            "repos_with_description": with_readme,
            "top_repos": [
                {
                    "name": r["name"],
                    "description": r.get("description"),
                    "language": r.get("language"),
                    "stars": r.get("stargazers_count", 0),
                    "url": r.get("html_url"),
                    "updated_at": r.get("updated_at"),
                }
                for r in top_repos
            ],
        }
