"""Database seeding services for initial admin user and demo projects."""

import logging
from core.config import settings
from core.security import hash_password, verify_password
from models.admin import AdminUser
from models.project import Project, ProjectStatus

logger = logging.getLogger(__name__)

DEMO_PROJECTS = [
    {
        "title": "Furniture Co. Marketing Site",
        "description": "A full redesign of a home-furnishings brand's website — new visual identity, a CMS the marketing team can run without a developer, and a checkout flow that cut cart abandonment noticeably in the first quarter post-launch.",
        "image_url": "https://images.unsplash.com/photo-1487014679447-9f8336841d58",
        "tags": ["Website"],
        "highlights": [
            "Custom web design with responsive layouts across devices",
            "Integrated headless CMS for quick marketing content updates",
            "Streamlined checkout process that increased conversion by 18%",
        ],
        "featured": True,
        "order": 0,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "Fintech SaaS Dashboard",
        "description": "A multi-tenant analytics dashboard for a fintech startup — real-time transaction insights, role-based access, and a component system built to support their next three product lines without a rebuild.",
        "image_url": "https://images.unsplash.com/photo-1686061594225-3e92c0cd51b0",
        "tags": ["SaaS", "Web App"],
        "highlights": [
            "Real-time transaction insights via WebSockets",
            "Advanced role-based access control (RBAC) security",
            "Reusable visual component library for scalability",
        ],
        "featured": True,
        "order": 1,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "Retail Mobile Companion App",
        "description": "A companion web app for a retail chain's loyalty program — browsing, rewards tracking, and push-style notifications, all in a lightweight interface their in-store staff also use on tablets.",
        "image_url": "https://images.unsplash.com/photo-1548094891-c4ba474efd16",
        "tags": ["Web App"],
        "highlights": [
            "Seamless loyalty rewards tracker interface",
            "Push notifications for active store promotions",
            "Optimized layout for fast tablet and mobile views",
        ],
        "featured": True,
        "order": 2,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "Growth Marketing Analytics Suite",
        "description": "An internal reporting suite pulling together paid, organic, and lifecycle email data into one view — replacing five disconnected spreadsheets with a single source of truth for the growth team.",
        "image_url": "https://images.pexels.com/photos/10020092/pexels-photo-10020092.jpeg",
        "tags": ["Marketing", "SaaS"],
        "highlights": [
            "Consolidated organic, paid, and email campaign data",
            "Interactive charting for quick performance analysis",
            "Custom API integrations with top marketing tools",
        ],
        "featured": False,
        "order": 3,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "Enterprise SAP Cloud Migration",
        "description": "A phased S/4HANA migration for a mid-size manufacturer — data validation, parallel testing, and a rollback plan at every stage, completed with zero unplanned downtime.",
        "image_url": "https://images.unsplash.com/photo-1762163516269-3c143e04175c",
        "tags": ["SAP"],
        "highlights": [
            "Zero unplanned downtime during transition stages",
            "Automatic data validation before migration batches",
            "Comprehensive roll-back plans for risk mitigation",
        ],
        "featured": True,
        "order": 4,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "Ops Workflow Automation Platform",
        "description": "An end-to-end automation layer connecting a logistics company's CRM, email, and internal tools — cutting manual data entry across their fulfillment pipeline by the majority of what a two-person team used to handle by hand.",
        "image_url": "https://images.pexels.com/photos/8386440/pexels-photo-8386440.jpeg",
        "tags": ["Workflow Automation"],
        "highlights": [
            "Reduced manual logistics entry tasks by 60%",
            "Seamless integrations between CRM and email clients",
            "Real-time pipeline exception monitoring and alerts",
        ],
        "featured": True,
        "order": 5,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "D2C Ecommerce Storefront Revamp",
        "description": "A ground-up storefront rebuild for a direct-to-consumer brand — faster load times, a streamlined checkout, and integrated email marketing that turned repeat purchase rate into their best-performing channel.",
        "image_url": "https://images.pexels.com/photos/6956903/pexels-photo-6956903.jpeg",
        "tags": ["Website", "Marketing"],
        "highlights": [
            "Lightning-fast page load times under 1.2s",
            "Streamlined product page layouts and filters",
            "Integrated automated lifecycle marketing triggers",
        ],
        "featured": False,
        "order": 6,
        "status": ProjectStatus.PUBLISHED,
    },
    {
        "title": "Internal Ops Dashboard for Logistics",
        "description": "A custom internal dashboard replacing a patchwork of spreadsheets for a logistics team — live shipment tracking, automated exception alerts, and a single view for a team that used to start every morning stitching reports together.",
        "image_url": "https://images.unsplash.com/photo-1560472354-b33ff0c44a43",
        "tags": ["SaaS", "Workflow Automation"],
        "highlights": [
            "Unified shipment tracking map interface",
            "Automated exception alerts for delayed packages",
            "Daily automated reporting compilation module",
        ],
        "featured": False,
        "order": 7,
        "status": ProjectStatus.PUBLISHED,
    },
]


async def seed_admin(db):
    """Provisions or updates admin account based on environment configuration."""
    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD

    if not email or not password:
        if settings.IS_PRODUCTION:
            logger.info("ADMIN_EMAIL or ADMIN_PASSWORD not provided; skipping automatic seeder in production.")
            return
        # Safe development default
        email = "admin@navigatte.com"
        password = "Navigatte@Admin2026"

    email_clean = email.lower().strip()
    existing = await db.admin_users.find_one({"email": email_clean})

    if existing is None:
        admin = AdminUser(email=email_clean, password_hash=hash_password(password))
        await db.admin_users.insert_one(admin.to_mongo())
        logger.info(f"Seeded admin user: {email_clean}")
    elif not verify_password(password, existing.get("password_hash", "")):
        await db.admin_users.update_one(
            {"email": email_clean},
            {"$set": {"password_hash": hash_password(password)}},
        )
        logger.info(f"Updated password for admin user: {email_clean}")


async def seed_demo_projects(db):
    """Seeds initial showcase projects if collection is currently empty."""
    existing_count = await db.projects.count_documents({})
    if existing_count == 0:
        docs = []
        for item in DEMO_PROJECTS:
            project = Project(**item)
            docs.append(project.to_mongo())
        if docs:
            await db.projects.insert_many(docs)
            logger.info(f"Seeded {len(docs)} demo projects.")
