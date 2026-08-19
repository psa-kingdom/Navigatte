import React, { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus, Pencil, Trash2, LogOut, Star, LayoutDashboard, Inbox, FolderOpen } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { Button } from "@/components/ui/button";
import Logo from "@/components/layout/Logo";
import ProjectFormDialog from "@/components/admin/ProjectFormDialog";
import StatsGrid from "@/components/admin/overview/StatsGrid";
import EnquiriesCRM from "@/components/admin/enquiries/EnquiriesCRM";
import api from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

// ---------------------------------------------------------------------------
// Nav tabs
// ---------------------------------------------------------------------------
const TABS = [
  { value: "overview",   label: "Overview",   Icon: LayoutDashboard },
  { value: "enquiries",  label: "Enquiries",  Icon: Inbox },
  { value: "projects",   label: "Projects",   Icon: FolderOpen },
];

const tabVariants = {
  hidden: { opacity: 0, y: 10 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } },
  exit:   { opacity: 0, y: -6, transition: { duration: 0.15 } },
};

// ---------------------------------------------------------------------------
// Overview tab — stats + quick actions
// ---------------------------------------------------------------------------
const OverviewTab = ({ stats, statsLoading, onTabChange }) => {
  const date = new Date().toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <motion.div key="overview" variants={tabVariants} initial="hidden" animate="show" exit="exit"
      className="space-y-8"
    >
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-display font-light text-cloud">Command Center</h1>
        <p className="text-sm text-fog mt-1">{date}</p>
      </div>

      {/* Stats cards */}
      <div>
        <h2 className="text-xs font-medium text-fog uppercase tracking-wider mb-4">At a Glance</h2>
        <StatsGrid stats={stats} loading={statsLoading} onTabChange={onTabChange} />
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="text-xs font-medium text-fog uppercase tracking-wider mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Button
            onClick={() => onTabChange("enquiries")}
            variant="outline"
            className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 rounded-lg"
          >
            <Inbox className="w-4 h-4 mr-2" />
            View Enquiries
          </Button>
          <Button
            onClick={() => onTabChange("projects")}
            variant="outline"
            className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 rounded-lg"
          >
            <FolderOpen className="w-4 h-4 mr-2" />
            Manage Projects
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

// ---------------------------------------------------------------------------
// Projects tab — full CRUD table
// ---------------------------------------------------------------------------
const ProjectsTab = () => {
  const { toast } = useToast();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tags, setTags] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const STATUS_COLORS = {
    published: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
    draft:     "bg-iris/15 text-iris border-iris/25",
    archived:  "bg-white/5 text-fog border-white/10",
  };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [projectsRes, tagsRes] = await Promise.all([
        api.get("/admin/projects"),
        api.get("/tags"),
      ]);
      setProjects(projectsRes.data);
      setTags(tagsRes.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleDelete = async (project) => {
    setDeletingId(project.id);
    try {
      await api.delete(`/projects/${project.id}`);
      toast({ title: "Project deleted" });
      fetchAll();
    } catch {
      toast({ title: "Failed to delete project", variant: "destructive" });
    } finally {
      setDeletingId(null);
    }
  };

  const featuredCount = projects.filter((p) => p.featured).length;

  return (
    <motion.div key="projects" variants={tabVariants} initial="hidden" animate="show" exit="exit"
      className="space-y-6"
    >
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-display font-light text-cloud">Projects</h2>
          <p className="text-sm text-ash mt-1">
            {projects.length} total · {featuredCount}/5 featured on homepage
          </p>
        </div>
        <Button
          onClick={() => { setEditing(null); setFormOpen(true); }}
          data-testid="admin-add-project-button"
          className="bg-pure text-void hover:bg-cloud rounded-lg h-10"
        >
          <Plus className="w-4 h-4" /> Add Project
        </Button>
      </div>

      {/* Grid */}
      {loading ? (
        <p className="text-ash" data-testid="admin-projects-loading">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="text-ash" data-testid="admin-projects-empty">
          No projects yet. Add your first one.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((project) => (
            <div
              key={project.id}
              data-testid={`admin-project-card-${project.id}`}
              className="bg-graphite/50 border border-white/10 rounded-feature overflow-hidden"
            >
              <div className="relative aspect-[16/10]">
                <img
                  src={project.image_url}
                  alt={project.title}
                  className="w-full h-full object-cover"
                />
                {project.featured && (
                  <span className="absolute top-3 left-3 flex items-center gap-1 bg-iris text-white 
                                   text-[10px] font-mono-label rounded-pill px-2.5 py-1">
                    <Star className="w-3 h-3" /> Featured
                  </span>
                )}
              </div>
              <div className="p-5">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="text-base font-medium text-cloud">{project.title}</h3>
                  {/* Status badge */}
                  <span className={`flex-shrink-0 border rounded-lg px-2 py-0.5 text-[10px] font-medium 
                                   ${STATUS_COLORS[project.status] ?? STATUS_COLORS.draft}`}>
                    {project.status ?? "draft"}
                  </span>
                </div>
                {project.slug && (
                  <p className="text-xs text-fog font-mono mb-2">/{project.slug}</p>
                )}
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {project.tags?.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] text-ash bg-white/5 border border-white/10 rounded-pill px-2 py-0.5"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <Button
                    onClick={() => { setEditing(project); setFormOpen(true); }}
                    data-testid={`admin-edit-project-${project.id}`}
                    variant="outline"
                    size="sm"
                    className="border-white/20 text-cloud hover:bg-white/5 rounded-lg flex-1"
                  >
                    <Pencil className="w-3.5 h-3.5" /> Edit
                  </Button>
                  <Button
                    onClick={() => handleDelete(project)}
                    disabled={deletingId === project.id}
                    data-testid={`admin-delete-project-${project.id}`}
                    variant="outline"
                    size="sm"
                    className="border-destructive/40 text-destructive hover:bg-destructive/10 rounded-lg"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <ProjectFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        project={editing}
        availableTags={tags}
        onSaved={fetchAll}
      />
    </motion.div>
  );
};

// ---------------------------------------------------------------------------
// Main AdminCommandCenterPage
// ---------------------------------------------------------------------------
const AdminCommandCenterPage = () => {
  const { admin, logout } = useAdminAuth();
  const [activeTab, setActiveTab] = useState(
    () => sessionStorage.getItem("admin_tab") ?? "overview"
  );
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const resp = await api.get("/admin/stats");
      setStats(resp.data);
    } catch {
      // Stats are non-critical — fail silently
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    sessionStorage.setItem("admin_tab", tab);
    // Refresh stats when switching to overview
    if (tab === "overview") fetchStats();
  };

  return (
    <div className="min-h-screen bg-obsidian">
      {/* Sticky header */}
      <header className="border-b border-white/10 sticky top-0 bg-obsidian/90 backdrop-blur-md z-10">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <Logo />

            {/* Tab navigation */}
            <nav className="hidden sm:flex items-center gap-1">
              {TABS.map(({ value, label, Icon }) => (
                <button
                  key={value}
                  onClick={() => handleTabChange(value)}
                  data-testid={`admin-tab-${value}`}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm transition-colors
                              ${activeTab === value
                                ? "bg-white/8 text-cloud font-medium"
                                : "text-fog hover:text-ash hover:bg-white/5"}`}
                >
                  <Icon className="w-3.5 h-3.5" strokeWidth={1.8} />
                  {label}
                </button>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <span data-testid="admin-user-email" className="text-sm text-ash hidden md:inline">
              {admin?.email}
            </span>
            <Button
              onClick={logout}
              data-testid="admin-logout-button"
              variant="outline"
              className="border-white/20 text-cloud hover:bg-white/5 rounded-lg h-9"
            >
              <LogOut className="w-4 h-4" /> Log Out
            </Button>
          </div>
        </div>

        {/* Mobile tab bar */}
        <div className="sm:hidden flex border-t border-white/8">
          {TABS.map(({ value, label, Icon }) => (
            <button
              key={value}
              onClick={() => handleTabChange(value)}
              className={`flex-1 flex flex-col items-center gap-1 py-2.5 text-xs transition-colors
                          ${activeTab === value ? "text-cloud border-t-2 border-iris" : "text-fog"}`}
            >
              <Icon className="w-4 h-4" strokeWidth={1.8} />
              {label}
            </button>
          ))}
        </div>
      </header>

      {/* Tab content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <AnimatePresence mode="wait">
          {activeTab === "overview" && (
            <OverviewTab
              stats={stats}
              statsLoading={statsLoading}
              onTabChange={handleTabChange}
            />
          )}
          {activeTab === "enquiries" && (
            <motion.div key="enquiries" variants={tabVariants} initial="hidden" animate="show" exit="exit">
              <div className="mb-6">
                <h2 className="text-xl font-display font-light text-cloud">Enquiries</h2>
                <p className="text-sm text-ash mt-1">Manage incoming leads and the CRM pipeline</p>
              </div>
              <EnquiriesCRM />
            </motion.div>
          )}
          {activeTab === "projects" && <ProjectsTab />}
        </AnimatePresence>
      </main>
    </div>
  );
};

export default AdminCommandCenterPage;
