"""Tests for file import parser (.xlsx, .csv, .txt) and immediate campaign dispatch."""

import io
from datetime import datetime, timezone
import openpyxl
import pandas as pd
import pytest
from core.database import get_database
from models.campaign import CampaignModel, CampaignStatus


@pytest.mark.asyncio
async def test_parse_import_file_xlsx(client, auth_headers):
    """Verifies that an Excel .xlsx file with multi-column emails is parsed cleanly without garbage data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append(["Name", "Organization", "Contact Email", "Notes"])
    ws.append(["Sarah Connor", "Cyberdyne", "sarah@cyberdyne.io", "VIP"])
    ws.append(["John Reese", "Acme Corp", "john.reese@acme.com", "Secondary"])
    ws.append(["Duplicate Entry", "Acme Corp", "sarah@cyberdyne.io", "Duplicate"])

    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_bytes = excel_buffer.getvalue()

    files = {"file": ("test_contacts.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/admin/communications/parse-import-file", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert data["filename"] == "test_contacts.xlsx"
    assert data["valid_count"] == 2
    assert "sarah@cyberdyne.io" in data["valid_emails"]
    assert "john.reese@acme.com" in data["valid_emails"]
    assert data["duplicate_count"] == 1


@pytest.mark.asyncio
async def test_parse_import_file_csv(client, auth_headers):
    """Verifies that CSV files with multiple columns are correctly parsed."""
    csv_content = (
        "Name,Email,Company\n"
        "Alice,alice@example.com,Navigatte\n"
        "Bob,bob@enterprise.io,Enterprise\n"
        "Invalid Row,not-an-email,Test\n"
    )
    files = {"file": ("contacts.csv", csv_content.encode("utf-8"), "text/csv")}
    resp = client.post("/api/admin/communications/parse-import-file", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert data["valid_count"] == 2
    assert "alice@example.com" in data["valid_emails"]
    assert "bob@enterprise.io" in data["valid_emails"]
    assert data["invalid_count"] == 1


@pytest.mark.asyncio
async def test_immediate_campaign_launch_outbox_processing(client, auth_headers, monkeypatch):
    """Launching a campaign immediately triggers initial delivery worker batch."""
    from datetime import datetime, timezone
    from integrations.contracts.communications import EmailDeliveryResult

    async def mock_send(self, message):
        return EmailDeliveryResult(
            provider="resend",
            message_id="msg_launch_test_123",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )

    from core.config import settings
    settings.RESEND_ENABLED = True

    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.send_email", mock_send)
    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.is_enabled", lambda self: True)

    db = get_database()
    # Create campaign
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Immediate Launch Test",
        "environment": "production",
        "subject": "Immediate Dispatch",
        "custom_html": "<p>Hello {{ name }}</p>",
        "audience_source": "manual",
        "manual_recipients": ["recipient1@enterprise.com", "recipient2@enterprise.com"],
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    # Launch campaign
    launch_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/launch", headers=auth_headers)
    assert launch_resp.status_code == 200
    launch_data = launch_resp.json()
    assert launch_data["success"] is True
    assert launch_data["campaign"]["status"] in ("sending", "completed")

    # Verify outbox items were created
    outbox_docs = await db.email_outbox.find({"metadata.campaign_id": camp_id}).to_list(10)
    assert len(outbox_docs) == 2

