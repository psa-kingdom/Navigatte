import {
  LayoutDashboard,
  Inbox,
  FolderOpen,
  Mail,
  BarChart3,
  Settings,
  Sparkles,
} from "lucide-react";

/**
 * Single source of truth for Navigatte Admin Navigation.
 * Adding new modules or adjusting access routes happens here.
 */
export const ADMIN_NAV_SECTIONS = [
  {
    category: "Operations",
    items: [
      {
        id: "overview",
        label: "Command Center",
        icon: LayoutDashboard,
        badge: null,
        status: "active",
        description: "Operational metrics, quick actions & system status",
      },
      {
        id: "enquiries",
        label: "Enquiries & Leads",
        icon: Inbox,
        badge: "CRM",
        status: "active",
        description: "5-stage sales pipeline, contact details & notes",
      },
    ],
  },
  {
    category: "Content & Growth",
    items: [
      {
        id: "projects",
        label: "Projects & Showcase",
        icon: FolderOpen,
        badge: "CMS",
        status: "active",
        description: "Portfolio case studies, publication lifecycle & SEO",
      },
      {
        id: "communications",
        label: "Communications",
        icon: Mail,
        badge: "Studio",
        status: "active",
        description: "Transactional templates, outbox delivery & Resend telemetry",
      },
      {
        id: "analytics",
        label: "Analytics",
        icon: BarChart3,
        badge: "Phase 2B",
        status: "coming-soon",
        description: "Traffic insights, inquiry conversion & portfolio reach",
      },
    ],
  },
  {
    category: "Platform",
    items: [
      {
        id: "settings",
        label: "Settings & Health",
        icon: Settings,
        badge: "Control Centre",
        status: "active",
        description: "Integrations, system diagnostics, appearance & admin security",
      },
    ],
  },
];

/** Flattened list of all navigation items */
export const ADMIN_NAV_ITEMS = ADMIN_NAV_SECTIONS.flatMap(
  (section) => section.items
);

/** Active navigation IDs that can be navigated to */
export const ACTIVE_NAV_IDS = ADMIN_NAV_ITEMS.filter(
  (item) => item.status === "active"
).map((item) => item.id);
