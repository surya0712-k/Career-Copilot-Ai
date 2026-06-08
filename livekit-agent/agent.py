import os

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, inference
from livekit.plugins import openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()

DEFAULT_INSTRUCTIONS = """You are a senior software engineer conducting a mock technical interview.
Rules:
- Ask ONE question at a time, then wait for the candidate to answer
- Mix behavioral and technical questions appropriate for the target role
- Keep responses concise and spoken naturally (2-4 sentences max)
- After each answer, give brief constructive feedback before the next question
- Be professional but encouraging
- Do not answer questions on behalf of the candidate
"""


def _azure_base_url() -> str:
    endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT", "").rstrip("/")
    if "/api/projects/" in endpoint:
        from urllib.parse import urlparse

        parsed = urlparse(endpoint)
        endpoint = f"{parsed.scheme}://{parsed.netloc}/openai/v1"
    for suffix in ("/chat/completions", "/embeddings"):
        if endpoint.endswith(suffix):
            endpoint = endpoint[: -len(suffix)]
    return endpoint


def _build_instructions() -> str:
    company = os.getenv("INTERVIEW_COMPANY", "the company")
    role = os.getenv("INTERVIEW_ROLE", "Software Engineer")
    level = os.getenv("INTERVIEW_LEVEL", "internship")
    extra = os.getenv("INTERVIEW_CONTEXT", "")
    return (
        f"{DEFAULT_INSTRUCTIONS}\n\n"
        f"Target role: {role} at {company} ({level}).\n"
        f"{extra}"
    ).strip()


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    metadata = ctx.job.metadata or ""
    if metadata:
        os.environ["INTERVIEW_CONTEXT"] = metadata

    llm_model = os.getenv("LLM_MODEL", "")
    azure_endpoint = _azure_base_url()
    azure_key = os.getenv("AZURE_FOUNDRY_API_KEY", "")

    if not llm_model or not azure_endpoint or not azure_key:
        raise RuntimeError(
            "Voice agent requires LLM_MODEL, AZURE_FOUNDRY_ENDPOINT, and AZURE_FOUNDRY_API_KEY"
        )

    stt_model = os.getenv("LIVEKIT_STT_MODEL", "deepgram/nova-3")
    tts_model = os.getenv("LIVEKIT_TTS_MODEL", "cartesia/sonic-2")

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=inference.STT(stt_model, language="en"),
        llm=openai.LLM(model=llm_model, base_url=azure_endpoint, api_key=azure_key),
        tts=inference.TTS(tts_model),
        turn_detection=MultilingualModel(),
    )

    agent = Agent(instructions=_build_instructions())

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        if participant.identity != ctx.room.local_participant.identity:
            if not ctx.room.remote_participants:
                ctx.shutdown()

    await session.start(agent=agent, room=ctx.room)

    await session.generate_reply(
        instructions="Introduce yourself briefly as the interviewer and ask your first question."
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="career-interviewer",
        )
    )
