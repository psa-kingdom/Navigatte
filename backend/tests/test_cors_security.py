"""Regression tests for CORS policies, cross-site origin handling, and authentication preflight."""

import pytest
from core.config import settings

# Test Origins
PROD_ORIGIN = "https://navigatte.com"
PROD_WWW_ORIGIN = "https://www.navigatte.com"
PROD_VERCEL_ALIAS = "https://navigatte-website.vercel.app"

# Vercel preview origins (matching scoped pattern)
PREVIEW_HASH_ORIGIN = "https://navigatte-website-dz050ctkg-psumanassociates-9980s-projects.vercel.app"
PREVIEW_BRANCH_ORIGIN = "https://navigatte-website-git-test-psumanassociates-9980s-projects.vercel.app"

# Local development origins
LOCAL_DEV_ORIGIN = "http://localhost:3000"

# Untrusted origins
UNTRUSTED_EXTERNAL = "https://malicious-attacker.com"
UNTRUSTED_ARBITRARY_VERCEL = "https://arbitrary-project.vercel.app"
UNTRUSTED_FORGED_TEAM = "https://evil-psumanassociates-9980s-projects.vercel.app"


def test_cors_preflight_production_origin(client):
    """OPTIONS preflight from production custom domains must succeed and return credentials."""
    headers = {
        "Origin": PROD_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    }
    resp = client.options("/api/auth/login", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == PROD_ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_vercel_preview_origin(client):
    """OPTIONS preflight from trusted Vercel Preview URL must match regex and return CORS headers."""
    headers = {
        "Origin": PREVIEW_HASH_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    }
    resp = client.options("/api/auth/login", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == PREVIEW_HASH_ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_vercel_branch_preview_origin(client):
    """OPTIONS preflight from Git branch Vercel Preview must succeed."""
    headers = {
        "Origin": PREVIEW_BRANCH_ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    resp = client.options("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == PREVIEW_BRANCH_ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_local_development_origin(client):
    """OPTIONS preflight from localhost:3000 must succeed."""
    headers = {
        "Origin": LOCAL_DEV_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    resp = client.options("/api/auth/login", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == LOCAL_DEV_ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_untrusted_origin_rejected(client):
    """Untrusted origins must NOT receive Access-Control-Allow-Origin headers."""
    for untrusted in (UNTRUSTED_EXTERNAL, UNTRUSTED_ARBITRARY_VERCEL, UNTRUSTED_FORGED_TEAM):
        headers = {
            "Origin": untrusted,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        resp = client.options("/api/auth/login", headers=headers)
        # CORSMiddleware will not echo untrusted origins in Allow-Origin
        assert resp.headers.get("access-control-allow-origin") != untrusted


def test_cross_origin_login_and_auth_flow(client, test_admin_user):
    """Verifies that an allowed Preview origin can perform full login and subsequent auth requests."""
    # 1. Login from Preview origin
    login_payload = {
        "email": test_admin_user["email"],
        "password": test_admin_user["password"],
    }
    login_resp = client.post(
        "/api/auth/login",
        json=login_payload,
        headers={"Origin": PREVIEW_HASH_ORIGIN},
    )
    assert login_resp.status_code == 200
    assert login_resp.headers.get("access-control-allow-origin") == PREVIEW_HASH_ORIGIN
    assert login_resp.headers.get("access-control-allow-credentials") == "true"

    data = login_resp.json()
    assert "access_token" in data
    token = data["access_token"]

    # 2. Subsequent GET /api/auth/me using Bearer header from Preview origin
    me_resp = client.get(
        "/api/auth/me",
        headers={
            "Origin": PREVIEW_HASH_ORIGIN,
            "Authorization": f"Bearer {token}",
        },
    )
    assert me_resp.status_code == 200
    assert me_resp.headers.get("access-control-allow-origin") == PREVIEW_HASH_ORIGIN
    assert me_resp.json()["email"] == test_admin_user["email"]


def test_admin_overview_and_stats_alias_contract(client, auth_headers):
    """Verifies both /api/admin/overview and /api/admin/stats return the expected overview aggregate data."""
    stats_resp = client.get("/api/admin/stats", headers=auth_headers)
    overview_resp = client.get("/api/admin/overview", headers=auth_headers)

    assert stats_resp.status_code == 200
    assert overview_resp.status_code == 200

    stats_data = stats_resp.json()
    overview_data = overview_resp.json()

    assert stats_data == overview_data
    assert "enquiries_new" in overview_data
    assert "enquiries_pipeline" in overview_data
    assert "projects_total" in overview_data
    assert "projects_published" in overview_data
