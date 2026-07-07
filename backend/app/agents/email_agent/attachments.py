"""Gmail attachment PDF text extraction for Email Agent."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from app.agents.email_agent import settings as agent_settings
from app.ai.tools.gmail_tool import AttachmentInfo, EmailThreadConversation, ThreadMessage

logger = logging.getLogger(__name__)


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def fetch_attachment_bytes(service, message_id: str, attachment_id: str) -> bytes:
    result = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    data = result.get("data") or ""
    return base64.urlsafe_b64decode(data)


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str | None, str | None]:
    """Return (text, note). Note is set when text cannot be extracted."""
    if len(pdf_bytes) > agent_settings.MAX_PDF_BYTES:
        return None, f"PDF too large ({_format_size(len(pdf_bytes))}) — not extracted"

    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf not installed — PDF text extraction skipped")
        return None, "PDF text extraction unavailable"

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[: agent_settings.MAX_PDF_PAGES]
        chunks: list[str] = []
        total = 0
        for page in pages:
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            remaining = agent_settings.MAX_PDF_TEXT_CHARS - total
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = text[:remaining] + "\n...[truncated]"
            chunks.append(text)
            total += len(text)

        combined = "\n\n".join(chunks).strip()
        if combined:
            return combined, None
        return None, "scanned — no extractable text"
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return None, "could not extract PDF text"


def enrich_message_attachments(service, message: ThreadMessage) -> None:
    """Download and extract PDF text for attachments on a single message."""
    if not message.attachments:
        return

    pdf_count = 0
    for attachment in message.attachments:
        if attachment.mime_type != "application/pdf" and not attachment.filename.lower().endswith(
            ".pdf"
        ):
            continue
        if pdf_count >= agent_settings.MAX_PDFS_PER_MESSAGE:
            attachment.extract_note = "PDF limit reached for this message"
            continue

        pdf_count += 1
        if not attachment.attachment_id:
            continue

        try:
            pdf_bytes = fetch_attachment_bytes(
                service,
                message.email_id,
                attachment.attachment_id,
            )
            text, note = extract_pdf_text(pdf_bytes)
            attachment.extracted_text = text
            attachment.extract_note = note
        except Exception as exc:
            logger.warning(
                "Failed to fetch attachment %s on %s: %s",
                attachment.filename,
                message.email_id,
                exc,
            )
            attachment.extract_note = "could not download attachment"


def enrich_conversation_attachments(
    service,
    conversation: EmailThreadConversation,
) -> None:
    """Enrich all messages in a thread with PDF text (draft/display only)."""
    for message in conversation.messages:
        enrich_message_attachments(service, message)


def format_attachment_lines(message: ThreadMessage) -> list[str]:
    """Format attachment metadata and PDF text for prompts or API previews."""
    if not message.attachments:
        return []

    lines: list[str] = []
    meta = ", ".join(
        f"{attachment.filename} ({_format_size(attachment.size_bytes)})"
        for attachment in message.attachments
    )
    lines.append(f"Attachments: {meta}")

    for attachment in message.attachments:
        if attachment.extracted_text:
            lines.append(f"PDF content ({attachment.filename}):\n{attachment.extracted_text}")
        elif attachment.extract_note:
            lines.append(f"{attachment.filename}: {attachment.extract_note}")

    return lines


def attachments_to_api(message: ThreadMessage) -> list[dict[str, Any]]:
    """Serialize attachments for the frontend API."""
    result: list[dict[str, Any]] = []
    for attachment in message.attachments:
        preview = attachment.extracted_text
        if preview and len(preview) > 500:
            preview = preview[:500] + "…"
        result.append(
            {
                "filename": attachment.filename,
                "mimeType": attachment.mime_type,
                "size": attachment.size_bytes,
                "extractedTextPreview": preview,
                "extractNote": attachment.extract_note,
            }
        )
    return result
