"""
Integration tests for Projects/Portfolio CMS feature + Admin auth against a live backend.
Covers: /api/projects CRUD, /api/tags, /api/auth/* (login/logout/me),
brute-force lockout, and unauthenticated access protection.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api" if BASE_URL else None

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@navigatte.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Navigatte@Admin2026")


@pytest.fixture
def api_client():
    if not API:
        pytest.skip("REACT_APP_BACKEND_URL environment variable not set; skipping live server integration tests.")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client):
    resp = api_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed - skipping authenticated tests: {resp.text}")
    return api_client


class TestPublicProjects:
    def test_list_projects_returns_8_seeded(self, api_client):
        resp = api_client.get(f"{API}/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 8
        for p in data:
            assert "id" in p and isinstance(p["id"], str)
            assert "_id" not in p
            assert "title" in p and "description" in p and "image_url" in p

    def test_list_featured_projects(self, api_client):
        resp = api_client.get(f"{API}/projects", params={"featured": True})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5
        for p in data:
            assert p["featured"] is True

    def test_filter_by_tag(self, api_client):
        resp = api_client.get(f"{API}/projects", params={"tag": "SAP"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for p in data:
            assert "SAP" in p["tags"]

    def test_get_single_project(self, api_client):
        resp = api_client.get(f"{API}/projects")
        project_id = resp.json()[0]["id"]
        get_resp = api_client.get(f"{API}/projects/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == project_id

    def test_get_nonexistent_project_404(self, api_client):
        resp = api_client.get(f"{API}/projects/000000000000000000000000")
        assert resp.status_code == 404

    def test_list_tags(self, api_client):
        resp = api_client.get(f"{API}/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert "SAP" in tags
        assert "Website" in tags


class TestAuthSecurity:
    def test_unauthenticated_create_returns_401(self, api_client):
        resp = api_client.post(f"{API}/projects", json={
            "title": "TEST_hack", "description": "x", "image_url": "https://x.com/a.jpg"
        })
        assert resp.status_code == 401

    def test_unauthenticated_update_returns_401(self, api_client):
        list_resp = api_client.get(f"{API}/projects")
        project_id = list_resp.json()[0]["id"]
        resp = api_client.put(f"{API}/projects/{project_id}", json={"title": "hacked"})
        assert resp.status_code == 401

    def test_unauthenticated_delete_returns_401(self, api_client):
        list_resp = api_client.get(f"{API}/projects")
        project_id = list_resp.json()[0]["id"]
        resp = api_client.delete(f"{API}/projects/{project_id}")
        assert resp.status_code == 401

    def test_me_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(f"{API}/auth/me")
        assert resp.status_code == 401

    def test_login_wrong_password(self, api_client):
        resp = api_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert resp.status_code == 401
        assert "detail" in resp.json()

    def test_login_wrong_email(self, api_client):
        resp = api_client.post(f"{API}/auth/login", json={"email": "nope@x.com", "password": ADMIN_PASSWORD})
        assert resp.status_code == 401

    def test_login_correct_credentials_sets_cookies(self, api_client):
        resp = api_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == ADMIN_EMAIL
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    def test_me_after_login(self, authenticated_client):
        resp = authenticated_client.get(f"{API}/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == ADMIN_EMAIL

    def test_logout_clears_session(self, authenticated_client):
        resp = authenticated_client.post(f"{API}/auth/logout")
        assert resp.status_code == 200
        me_resp = authenticated_client.get(f"{API}/auth/me")
        assert me_resp.status_code == 401


class TestBruteForceLockout:
    def test_lockout_after_5_failed_attempts(self, api_client):
        email = "bruteforce_test@navigatte.com"
        for _ in range(5):
            resp = api_client.post(f"{API}/auth/login", json={"email": email, "password": "wrong"})
            assert resp.status_code == 401
        resp6 = api_client.post(f"{API}/auth/login", json={"email": email, "password": "wrong"})
        assert resp6.status_code == 429


class TestProjectCRUD:
    def test_create_update_delete_project_lifecycle(self, authenticated_client):
        create_payload = {
            "title": "TEST_Project_CRUD",
            "description": "A test project for CRUD verification",
            "image_url": "https://images.unsplash.com/photo-test",
            "tags": ["Website", "TEST_custom_tag"],
            "featured": False,
            "order": 99,
        }
        create_resp = authenticated_client.post(f"{API}/projects", json=create_payload)
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["title"] == create_payload["title"]
        assert "id" in created
        project_id = created["id"]

        get_resp = authenticated_client.get(f"{API}/projects/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == create_payload["title"]

        list_resp = authenticated_client.get(f"{API}/projects")
        ids = [p["id"] for p in list_resp.json()]
        assert project_id in ids

        update_resp = authenticated_client.put(f"{API}/projects/{project_id}", json={
            "title": "TEST_Project_Updated", "featured": True
        })
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["title"] == "TEST_Project_Updated"
        assert updated["featured"] is True

        del_resp = authenticated_client.delete(f"{API}/projects/{project_id}")
        assert del_resp.status_code == 200

        get_resp3 = authenticated_client.get(f"{API}/projects/{project_id}")
        assert get_resp3.status_code == 404

    def test_update_nonexistent_project_404(self, authenticated_client):
        resp = authenticated_client.put(f"{API}/projects/000000000000000000000000", json={"title": "x"})
        assert resp.status_code == 404

    def test_delete_nonexistent_project_404(self, authenticated_client):
        resp = authenticated_client.delete(f"{API}/projects/000000000000000000000000")
        assert resp.status_code == 404
