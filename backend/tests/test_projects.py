"""Tests for Projects/Case Studies domain."""

import pytest


def test_list_public_projects(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 8
    for p in data:
        assert "id" in p and isinstance(p["id"], str)
        assert "_id" not in p
        assert "title" in p
        assert "slug" in p
        assert "image_url" in p


def test_list_featured_projects(client):
    resp = client.get("/api/projects", params={"featured": True})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for p in data:
        assert p["featured"] is True


def test_filter_by_tag(client):
    resp = client.get("/api/projects", params={"tag": "Website"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for p in data:
        assert "Website" in p["tags"]


def test_get_project_by_id_and_slug(client):
    list_resp = client.get("/api/projects")
    first_project = list_resp.json()[0]
    project_id = first_project["id"]
    project_slug = first_project["slug"]

    # Lookup by ID
    resp_by_id = client.get(f"/api/projects/{project_id}")
    assert resp_by_id.status_code == 200
    assert resp_by_id.json()["id"] == project_id

    # Lookup by Slug
    if project_slug:
        resp_by_slug = client.get(f"/api/projects/{project_slug}")
        assert resp_by_slug.status_code == 200
        assert resp_by_slug.json()["id"] == project_id


def test_get_nonexistent_project_404(client):
    resp = client.get("/api/projects/000000000000000000000000")
    assert resp.status_code == 404


def test_unauthenticated_mutations_return_401(client):
    resp_create = client.post("/api/projects", json={"title": "Test", "description": "d", "image_url": "http://img"})
    assert resp_create.status_code == 401

    resp_update = client.put("/api/projects/000000000000000000000000", json={"title": "Test"})
    assert resp_update.status_code == 401

    resp_delete = client.delete("/api/projects/000000000000000000000000")
    assert resp_delete.status_code == 401


def test_project_crud_and_status_lifecycle(client, auth_headers):
    # 1. Admin creates a draft project
    create_payload = {
        "title": "Automated Logistics Hub Case Study",
        "description": "An end-to-end cloud platform for freight automation.",
        "image_url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d",
        "tags": ["Workflow Automation", "SaaS"],
        "highlights": [
            "Cut processing time by 45%",
            "Integrated real-time GPS tracking",
        ],
        "featured": False,
        "order": 99,
        "status": "draft",
    }
    create_resp = client.post("/api/projects", json=create_payload, headers=auth_headers)
    assert create_resp.status_code == 200
    created = create_resp.json()
    project_id = created["id"]
    assert created["title"] == create_payload["title"]
    assert created["slug"] == "automated-logistics-hub-case-study"
    assert created["status"] == "draft"

    # 2. Public /api/projects should NOT show draft projects
    public_resp = client.get("/api/projects")
    public_ids = [p["id"] for p in public_resp.json()]
    assert project_id not in public_ids

    # 3. Admin /api/admin/projects SHOULD show the draft project
    admin_list_resp = client.get("/api/admin/projects", headers=auth_headers)
    admin_ids = [p["id"] for p in admin_list_resp.json()]
    assert project_id in admin_ids

    # 4. Admin updates project status to published
    status_resp = client.patch(
        f"/api/admin/projects/{project_id}/status",
        params={"status": "published"},
        headers=auth_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "published"

    # 5. Public /api/projects should now show the published project
    public_resp2 = client.get("/api/projects")
    public_ids2 = [p["id"] for p in public_resp2.json()]
    assert project_id in public_ids2

    # 6. Admin updates project details
    update_resp = client.put(
        f"/api/projects/{project_id}",
        json={"title": "Updated Logistics Platform", "featured": True},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Logistics Platform"
    assert update_resp.json()["featured"] is True

    # 7. Admin deletes project
    del_resp = client.delete(f"/api/projects/{project_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json() == {"message": "Project deleted"}

    # Verify deleted
    get_resp = client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 404
