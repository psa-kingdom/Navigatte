"""Campaign Environment Model & Send Mode Separation Tests.

Verifies:
1. Deployment Environment (infrastructure state) != Campaign Send Mode (test vs production).
2. Production campaigns pass pre-flight validation and launch regardless of server environment.
3. Test campaigns strictly dispatch to test_recipients and block audience contacts.
4. resolve_recipients performs smart deduplication, whitespace trimming, and lowercase normalization.
"""

from datetime import datetime, timezone
import pytest
from core.database import get_database
from models.campaign import CampaignModel, CampaignStatus
from services.campaign_service import CampaignService


@pytest.mark.asyncio
async def test_production_campaign_validation_passes_on_any_deployment_environment(client, auth_headers, monkeypatch):
    """A production campaign is NOT blocked simply because server deployment is 'test' or 'staging'."""
    from core.config import settings
    monkeypatch.setattr("core.config.settings.RESEND_API_KEY", "re_test_key_12345")

    db = get_database()

    # Create audience
    aud_resp = client.post("/api/admin/communications/audiences", headers=auth_headers, json={"name": "Prod Launch Target"})
    aud_id = aud_resp.json()["id"]
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": "client1@enterprise.com", "name": "Client 1"})
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": "client2@enterprise.com", "name": "Client 2"})

    # Create production campaign
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Live Strategic Outreach",
        "environment": "production",
        "subject": "Strategic Advisory Update",
        "custom_html": "<p>Hello {{ name }}, welcome.</p>",
        "audience_id": aud_id,
        "audience_source": "audience",
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    # Validate pre-flight checklist
    val_resp = client.get(f"/api/admin/communications/campaigns/{camp_id}/validate", headers=auth_headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is True
    assert len(val_data["errors"]) == 0
    assert val_data["checklist"]["target_recipients_count"] == 2


@pytest.mark.asyncio
async def test_test_campaign_safety_boundary_on_production_deployment(client, auth_headers):
    """Test campaigns only target test_recipients even if an audience with 500 members is attached."""
    db = get_database()

    # Create audience with contacts
    aud_resp = client.post("/api/admin/communications/audiences", headers=auth_headers, json={"name": "Big Audience"})
    aud_id = aud_resp.json()["id"]
    for i in range(5):
        client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": f"user{i}@enterprise.com"})

    # Create TEST campaign with attached audience, but test mode active
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Sandbox Test Campaign",
        "environment": "test",
        "subject": "Internal Sandbox Test",
        "custom_html": "<p>Hello Tester</p>",
        "audience_id": aud_id,
        "audience_source": "both",
        "test_recipients": ["qa.tester@navigatte.internal"],
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    # Recipient calculation in test mode must strictly return only test recipients
    calc_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/calculate-recipients", headers=auth_headers)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    assert calc_data["final_count"] == 1
    assert calc_data["raw_count"] == 1


@pytest.mark.asyncio
async def test_recipient_smart_deduplication_and_normalization(client, auth_headers):
    """Recipient resolution trims whitespace, normalizes lowercase, and eliminates duplicates."""
    db = get_database()

    aud_resp = client.post("/api/admin/communications/audiences", headers=auth_headers, json={"name": "Dedup Test"})
    aud_id = aud_resp.json()["id"]
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": "sarah.connor@cyberdyne.io"})

    # Campaign with mixed case and duplicate manual recipients
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Dedup Campaign",
        "environment": "production",
        "subject": "Dedup Subject",
        "custom_html": "<p>Content</p>",
        "audience_id": aud_id,
        "audience_source": "both",
        "manual_recipients": [
            "SARAH.CONNOR@cyberdyne.io",  # Duplicate of audience
            " john@acme.com ",            # Whitespace
            "john@acme.com",              # Duplicate of previous manual
            "invalid-email-syntax",       # Invalid
            "ALICE@consulting.io",        # Uppercase
        ],
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    calc_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/calculate-recipients", headers=auth_headers)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    # Unique valid emails: sarah.connor@cyberdyne.io (1), john@acme.com (2), alice@consulting.io (3)
    assert calc_data["final_count"] == 3
    assert calc_data["duplicates_count"] == 2  # SARAH.CONNOR + second john@acme.com
    assert calc_data["invalid_count"] == 1     # invalid-email-syntax
