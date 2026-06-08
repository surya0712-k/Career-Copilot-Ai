from urllib.parse import urlparse

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings

settings = get_settings()


def _normalize_azure_foundry_endpoint(endpoint: str) -> tuple[str, dict[str, str] | None]:
    """Map Foundry portal URLs to an OpenAI-compatible base URL."""
    base = endpoint.rstrip("/")

    if "/api/projects/" in base:
        parsed = urlparse(base)
        base = f"{parsed.scheme}://{parsed.netloc}/openai/v1"

    # Strip accidental path suffixes (ChatOpenAI appends /chat/completions itself)
    for suffix in ("/chat/completions", "/embeddings"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]

    default_query = None
    if base.endswith("/models"):
        default_query = {"api-version": settings.azure_foundry_api_version}

    return base, default_query


def _azure_client_kwargs() -> dict:
    if not settings.azure_foundry_endpoint or not settings.azure_foundry_api_key:
        raise ValueError(
            "AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY are required. "
            "Deploy a model at https://ai.azure.com and copy the OpenAI-compatible endpoint."
        )
    base_url, default_query = _normalize_azure_foundry_endpoint(settings.azure_foundry_endpoint)
    kwargs: dict = {
        "api_key": settings.azure_foundry_api_key,
        "base_url": base_url,
    }
    if default_query:
        kwargs["default_query"] = default_query
    return kwargs


def get_llm() -> BaseChatModel:
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=0.3,
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
        **_azure_client_kwargs(),
    )


def get_embeddings() -> Embeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        **_azure_client_kwargs(),
    )
