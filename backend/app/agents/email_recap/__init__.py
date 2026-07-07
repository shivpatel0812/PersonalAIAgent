"""Scheduled email recap agent — scans inboxes and sends digest emails."""

from app.agents.email_recap.job import run_email_recap

__all__ = ["run_email_recap"]
