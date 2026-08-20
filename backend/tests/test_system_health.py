"""Tests for Admin System Health and Operational Centre Endpoints."""

import pytest
from models.system_health import HealthStatus


def test_system_health_unauthorized(client):
    """Unauthenticated requests must return 401."""
    resp = client.get("/api/admin/system/health")
    assert resp.status_code == 401


def test_system_health_authenticated(client, auth_headers):
    """Authenticated admin receives structured platform health report."""
    resp = client.get("/api/admin/system/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "overall_status" in data
    assert "integrations" in data
    assert len(data["integrations"]) >= 4

    providers = [i["provider"] for i in data["integrations"]]
    assert "mongodb" in providers
    assert "cal.com" in providers
    assert "resend" in providers
    assert "railway" in providers

    # MongoDB should be healthy in test harness
    mongo_record = next(i for i in data["integrations"] if i["provider"] == "mongodb")
    assert mongo_record["status"] == HealthStatus.HEALTHY.value
    assert mongo_record["connectivity"] == "connected"
    assert mongo_record["category"] == "database"
    assert mongo_record["latency_ms"] is not None


def test_database_connectivity_test_action(client, auth_headers):
    """POST /api/admin/system/health/database/test pings MongoDB and returns response."""
    resp = client.post("/api/admin/system/health/database/test", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["status"] == "connected"
    assert "latency_ms" in data
    assert "database_name" in data


def test_cal_connectivity_test_action(client, auth_headers, monkeypatch):
    """POST /api/admin/system/health/cal/test tests outbound Cal.com API."""
    # When CAL_API_KEY is unset
    monkeypatch.delenv("CAL_API_KEY", raising=False)
    monkeypatch.delenv("CAL_COM_API", raising=False)
    monkeypatch.delenv("CALCOM_API_KEY", raising=False)

    resp = client.post("/api/admin/system/health/cal/test", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
