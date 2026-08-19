"""Tests for authentication, session handling, and brute-force lockout."""

import pytest
from core.database import get_database


def test_login_success(client, test_admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": test_admin_user["email"], "password": test_admin_user["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_admin_user["email"]
    assert "access_token" in data
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


def test_login_wrong_password(client, test_admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": test_admin_user["email"], "password": "wrongpassword123"},
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_login_nonexistent_email(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@navigatte.com", "password": "anypassword"},
    )
    assert resp.status_code == 401


def test_auth_me_unauthenticated(client):
    # Clear any leftover cookies / headers
    client.cookies.clear()
    resp = client.get("/api/auth/me", headers={})
    assert resp.status_code == 401


def test_auth_me_authenticated(client, test_admin_user):
    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {test_admin_user['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_admin_user["email"]


def test_logout(client):
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Logged out"}


def test_brute_force_lockout(client):
    target_email = "bruteforce_target@navigatte.com"
    for _ in range(5):
        resp = client.post(
            "/api/auth/login",
            json={"email": target_email, "password": "invalidpassword"},
        )
        assert resp.status_code == 401

    # 6th attempt should be locked out with HTTP 429
    resp6 = client.post(
        "/api/auth/login",
        json={"email": target_email, "password": "invalidpassword"},
    )
    assert resp6.status_code == 429
    assert "Too many failed login attempts" in resp6.json().get("detail", "")
