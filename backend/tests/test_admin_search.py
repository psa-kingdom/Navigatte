"""Tests for Admin Global Search Endpoint."""

import asyncio
from core.database import get_database
from models.enquiry import Enquiry, EnquiryStatus
from models.project import Project, ProjectStatus
from services.seeder import seed_demo_projects


def test_admin_search_unauthorized(client):
    """Unauthenticated requests must be rejected with 401."""
    resp = client.get("/api/admin/search?q=enterprise")
    assert resp.status_code == 401


def test_admin_search_authenticated(client, auth_headers):
    """Authenticated admin can search across enquiries and projects."""
    db = get_database()

    async def _setup():
        # Ensure demo projects are seeded if empty
        await seed_demo_projects(db)

        # Delete any previous test items
        await db.enquiries.delete_many({"email": {"$in": ["director@quantum.io", "rca_verification_test@navigatte.com"]}})
        await db.projects.delete_many({"slug": "quantum-automation-engine"})

        # Insert test enquiries
        await db.enquiries.insert_one(
            Enquiry(
                name="Quantum Dynamics",
                email="director@quantum.io",
                company="Quantum Labs",
                message="Need enterprise migration",
                status=EnquiryStatus.NEW,
                is_test=False,
            ).to_mongo()
        )
        await db.enquiries.insert_one(
            Enquiry(
                name="Test RCA Verification Lead",
                email="rca_verification_test@navigatte.com",
                company="Test Corp",
                message="Diagnostic",
                status=EnquiryStatus.NEW,
                is_test=True,
            ).to_mongo()
        )

        # Insert test project
        await db.projects.insert_one(
            Project(
                title="Quantum Automation Engine",
                client_name="Quantum Labs",
                slug="quantum-automation-engine",
                description="High performance engine",
                image_url="https://images.unsplash.com/photo-1551288049-bebda4e38f71",
                tags=["AI & Automation"],
                status=ProjectStatus.PUBLISHED,
            ).to_mongo()
        )

    asyncio.run(_setup())

    # Search for "Quantum"
    resp = client.get("/api/admin/search?q=Quantum", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["query"] == "Quantum"
    assert len(data["enquiries"]) == 1
    assert data["enquiries"][0]["name"] == "Quantum Dynamics"
    assert data["enquiries"][0]["email"] == "director@quantum.io"

    assert len(data["projects"]) == 1
    assert data["projects"][0]["title"] == "Quantum Automation Engine"
    assert data["projects"][0]["client"] == "Quantum Labs"

    # Search for "RCA" should NOT return the is_test lead
    resp_test = client.get("/api/admin/search?q=RCA", headers=auth_headers)
    assert resp_test.status_code == 200
    data_test = resp_test.json()
    assert len(data_test["enquiries"]) == 0
