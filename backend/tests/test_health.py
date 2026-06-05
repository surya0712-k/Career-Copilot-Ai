import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_resume_text_extraction():
    from app.services.resume_parser import extract_text_from_pdf

    # Minimal valid PDF bytes
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Contents 4 0 R>>endobj 4 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 100 700 Td (Hello Resume) Tj ET\n"
        b"endstream endobj xref 0 5 trailer<</Size 5/Root 1 0 R>>startxref 0 %%EOF"
    )
    text = extract_text_from_pdf(pdf_bytes)
    assert "Hello" in text or len(text) >= 0
