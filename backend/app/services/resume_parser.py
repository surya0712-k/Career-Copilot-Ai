import io
from typing import Any

import fitz
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.llm import get_llm


class ExperienceItem(BaseModel):
    company: str = ""
    title: str = ""
    duration: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class ResumeParsed(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[dict[str, str]] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)


RESUME_PARSE_PROMPT = """You are an expert resume parser. Extract structured information from the resume text.
Be thorough with skills, technologies, experience, and projects. Return valid structured data only."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts).strip()


async def parse_resume(file_bytes: bytes) -> tuple[str, dict[str, Any]]:
    raw_text = extract_text_from_pdf(file_bytes)
    if not raw_text:
        raise ValueError("Could not extract text from PDF")

    llm = get_llm()
    structured_llm = llm.with_structured_output(ResumeParsed)
    result: ResumeParsed = await structured_llm.ainvoke(
        [
            SystemMessage(content=RESUME_PARSE_PROMPT),
            HumanMessage(content=f"Parse this resume:\n\n{raw_text[:12000]}"),
        ]
    )
    return raw_text, result.model_dump()
