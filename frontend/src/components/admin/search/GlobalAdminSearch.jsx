import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  X,
  Command,
  ArrowRight,
  FolderOpen,
  Inbox,
  LayoutDashboard,
  Plus,
  FileText,
  Clock,
  Sparkles,
  ExternalLink,
  Loader2,
  Calendar,
  Building2,
  Tag,
} from "lucide-react";
import { ADMIN_NAV_ITEMS, ADMIN_NAV_SECTIONS } from "@/config/adminNavigationConfig";
import api from "@/lib/api";

const STATUS_BADGES = {
  new: { label: "New", color: "bg-iris/15 text-iris border-iris/25" },
  contacted: { label: "Contacted", color: "bg-signal/15 text-signal border-signal/25" },
  qualified: { label: "Qualified", color: "bg-periwinkle/15 text-periwinkle border-periwinkle/25" },
  converted: { label: "Converted", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" },
  closed: { label: "Closed", color: "bg-white/5 text-ash border-white/10" },
  published: { label: "Published", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" },
  draft: { label: "Draft", color: "bg-iris/15 text-iris border-iris/25" },
  archived: { label: "Archived", color: "bg-white/5 text-fog border-white/10" },
};

export const GlobalAdminSearch = ({
  isOpen,
  onOpenChange,
  onSelectTab,
  onAction,
}) => {
  const [query, setQuery] = useState("");
  const [backendResults, setBackendResults] = useState({ enquiries: [], projects: [] });
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Global shortcut: Cmd/Ctrl + K to open
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenChange]);

  // Debounced backend entity search
  useEffect(() => {
    if (!query.trim()) {
      setBackendResults({ enquiries: [], projects: [] });
      setLoading(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const resp = await api.get(`/admin/search?q=${encodeURIComponent(query.trim())}&limit=5`);
        setBackendResults({
          enquiries: resp.data.enquiries || [],
          projects: resp.data.projects || [],
        });
      } catch (err) {
        setBackendResults({ enquiries: [], projects: [] });
      } finally {
        setLoading(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [query]);

  // Filter navigation items
  const matchedNavItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ADMIN_NAV_ITEMS.filter((i) => i.status === "active");
    return ADMIN_NAV_ITEMS.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.description?.toLowerCase().includes(q) ||
        item.category?.toLowerCase().includes(q)
    );
  }, [query]);

  // Predefined quick actions
  const quickActions = useMemo(() => {
    const q = query.trim().toLowerCase();
    const actions = [
      {
        id: "action-new-project",
        title: "Create New Project",
        subtitle: "Add a case study to portfolio",
        icon: Plus,
        tab: "projects",
        actionKey: "new-project",
      },
      {
        id: "action-view-enquiries",
        title: "View Enquiries Pipeline",
        subtitle: "Review incoming customer leads",
        icon: Inbox,
        tab: "enquiries",
      },
      {
        id: "action-overview",
        title: "Open Command Center",
        subtitle: "System overview and statistics",
        icon: LayoutDashboard,
        tab: "overview",
      },
    ];

    if (!q) return actions;
    return actions.filter(
      (a) => a.title.toLowerCase().includes(q) || a.subtitle.toLowerCase().includes(q)
    );
  }, [query]);

  // Flat list of selectable items for keyboard navigation
  const flatItems = useMemo(() => {
    const items = [];

    // 1. Navigation items
    matchedNavItems.forEach((nav) => {
      items.push({
        type: "navigation",
        id: `nav-${nav.id}`,
        title: nav.label,
        subtitle: nav.description,
        icon: nav.icon,
        badge: nav.badge,
        status: nav.status,
        tab: nav.id,
      });
    });

    // 2. Actions
    quickActions.forEach((act) => {
      items.push({
        type: "action",
        id: act.id,
        title: act.title,
        subtitle: act.subtitle,
        icon: act.icon,
        tab: act.tab,
        actionKey: act.actionKey,
      });
    });

    // 3. Enquiries
    backendResults.enquiries.forEach((enq) => {
      items.push({
        type: "enquiry",
        id: `enq-${enq.id}`,
        title: enq.name,
        subtitle: `${enq.email}${enq.company ? ` · ${enq.company}` : ""}`,
        icon: Inbox,
        status: enq.status,
        schedulingStatus: enq.scheduling_status,
        tab: "enquiries",
        data: enq,
      });
    });

    // 4. Projects
    backendResults.projects.forEach((proj) => {
      items.push({
        type: "project",
        id: `proj-${proj.id}`,
        title: proj.title,
        subtitle: `${proj.client ? `${proj.client} · ` : ""}${proj.slug || ""}`,
        icon: FolderOpen,
        status: proj.status,
        tab: "projects",
        data: proj,
      });
    });

    return items;
  }, [matchedNavItems, quickActions, backendResults]);

  // Keep selectedIndex within bounds
  useEffect(() => {
    setSelectedIndex((prev) => (flatItems.length === 0 ? 0 : Math.min(prev, flatItems.length - 1)));
  }, [flatItems]);

  const handleSelect = useCallback(
    (item) => {
      if (!item) return;
      onOpenChange(false);

      if (item.type === "navigation" || item.type === "action" || item.type === "enquiry" || item.type === "project") {
        if (item.status === "coming-soon") return;
        onSelectTab(item.tab);
        if (item.actionKey) {
          onAction?.(item.actionKey);
        }
      }
    },
    [onOpenChange, onSelectTab, onAction]
  );

  // Keyboard navigation inside modal
  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(flatItems.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + flatItems.length) % Math.max(flatItems.length, 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (flatItems[selectedIndex]) {
        handleSelect(flatItems[selectedIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onOpenChange(false);
    }
  };

  if (!isOpen) return null;

  const content = (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 pointer-events-none">
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        onClick={() => onOpenChange(false)}
        className="fixed inset-0 bg-void/80 backdrop-blur-md pointer-events-auto"
        aria-hidden="true"
        data-testid="admin-search-backdrop"
      />

      {/* Command Dialog Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: -8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -8 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="relative w-full max-w-2xl bg-obsidian border border-white/12 rounded-2xl shadow-2xl overflow-hidden z-10 flex flex-col pointer-events-auto max-h-[80vh]"
        role="dialog"
        aria-modal="true"
        aria-label="Global Admin Search"
        data-testid="global-admin-search-dialog"
      >
        {/* Search Bar Input */}
        <div className="p-4 border-b border-white/10 flex items-center gap-3 bg-graphite/40 flex-shrink-0">
          <Search className="w-5 h-5 text-fog flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command, search leads, projects, or sections..."
            data-testid="global-admin-search-input"
            className="flex-1 bg-transparent text-cloud placeholder:text-fog text-sm outline-none font-sans"
          />
          {loading && <Loader2 className="w-4 h-4 text-iris animate-spin flex-shrink-0" />}
          {query && (
            <button
              onClick={() => setQuery("")}
              className="w-5 h-5 rounded flex items-center justify-center text-fog hover:text-cloud transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center gap-0.5 text-[10px] font-mono text-fog bg-white/5 border border-white/10 px-1.5 py-0.5 rounded">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div ref={listRef} className="overflow-y-auto p-2 flex-1 divide-y divide-white/5">
          {flatItems.length === 0 ? (
            <div className="p-12 text-center text-fog space-y-2">
              <Search className="w-8 h-8 text-fog/40 mx-auto" />
              <p className="text-sm">No results found for &ldquo;{query}&rdquo;</p>
              <p className="text-xs text-fog/60">Try searching for &ldquo;enquiries&rdquo;, &ldquo;projects&rdquo;, or client names</p>
            </div>
          ) : (
            <div className="space-y-4 py-1">
              {/* 1. Navigation Section */}
              {matchedNavItems.length > 0 && (
                <div className="space-y-1">
                  <p className="px-3 py-1 text-[11px] font-mono uppercase tracking-wider text-fog">
                    Navigation
                  </p>
                  {matchedNavItems.map((nav) => {
                    const idx = flatItems.findIndex((i) => i.id === `nav-${nav.id}`);
                    const isSelected = idx === selectedIndex;
                    const Icon = nav.icon;
                    const isComingSoon = nav.status === "coming-soon";

                    return (
                      <button
                        key={nav.id}
                        onClick={() => handleSelect(flatItems[idx])}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        data-testid={`search-item-nav-${nav.id}`}
                        className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all ${
                          isSelected ? "bg-iris/15 text-cloud" : "text-ash hover:bg-white/5"
                        } ${isComingSoon ? "opacity-60 cursor-default" : "cursor-pointer"}`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            isSelected ? "bg-iris/25 text-iris" : "bg-white/5 text-fog"
                          }`}>
                            {Icon && <Icon className="w-4 h-4" />}
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-cloud truncate">{nav.label}</p>
                            <p className="text-[11px] text-fog truncate">{nav.description}</p>
                          </div>
                        </div>
                        {nav.badge && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-fog border border-white/10 ml-2">
                            {nav.badge}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* 2. Actions Section */}
              {quickActions.length > 0 && (
                <div className="space-y-1">
                  <p className="px-3 py-1 text-[11px] font-mono uppercase tracking-wider text-fog">
                    Quick Actions
                  </p>
                  {quickActions.map((act) => {
                    const idx = flatItems.findIndex((i) => i.id === act.id);
                    const isSelected = idx === selectedIndex;
                    const Icon = act.icon;

                    return (
                      <button
                        key={act.id}
                        onClick={() => handleSelect(flatItems[idx])}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        data-testid={`search-item-action-${act.id}`}
                        className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all cursor-pointer ${
                          isSelected ? "bg-iris/15 text-cloud" : "text-ash hover:bg-white/5"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            isSelected ? "bg-iris/25 text-iris" : "bg-white/5 text-fog"
                          }`}>
                            <Icon className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-cloud truncate">{act.title}</p>
                            <p className="text-[11px] text-fog truncate">{act.subtitle}</p>
                          </div>
                        </div>
                        <ArrowRight className="w-3.5 h-3.5 text-fog opacity-60" />
                      </button>
                    );
                  })}
                </div>
              )}

              {/* 3. CRM Enquiries */}
              {backendResults.enquiries.length > 0 && (
                <div className="space-y-1">
                  <p className="px-3 py-1 text-[11px] font-mono uppercase tracking-wider text-fog">
                    Enquiries & Leads ({backendResults.enquiries.length})
                  </p>
                  {backendResults.enquiries.map((enq) => {
                    const idx = flatItems.findIndex((i) => i.id === `enq-${enq.id}`);
                    const isSelected = idx === selectedIndex;
                    const statusCfg = STATUS_BADGES[enq.status] || STATUS_BADGES.new;

                    return (
                      <button
                        key={enq.id}
                        onClick={() => handleSelect(flatItems[idx])}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        data-testid={`search-item-enquiry-${enq.id}`}
                        className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all cursor-pointer ${
                          isSelected ? "bg-iris/15 text-cloud" : "text-ash hover:bg-white/5"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            isSelected ? "bg-iris/25 text-iris" : "bg-white/5 text-fog"
                          }`}>
                            <Inbox className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <p className="text-xs font-medium text-cloud truncate">{enq.name}</p>
                              {enq.scheduling_status === "booked" && (
                                <span className="inline-flex items-center gap-0.5 text-[9px] text-emerald-400 font-mono bg-emerald-500/10 px-1 py-0.2 rounded">
                                  <Calendar className="w-2.5 h-2.5" /> Booked
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-fog truncate">
                              {enq.email} {enq.company && `· ${enq.company}`}
                            </p>
                          </div>
                        </div>
                        <span className={`text-[10px] font-medium border rounded px-1.5 py-0.5 ${statusCfg.color}`}>
                          {statusCfg.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* 4. Projects */}
              {backendResults.projects.length > 0 && (
                <div className="space-y-1">
                  <p className="px-3 py-1 text-[11px] font-mono uppercase tracking-wider text-fog">
                    Projects ({backendResults.projects.length})
                  </p>
                  {backendResults.projects.map((proj) => {
                    const idx = flatItems.findIndex((i) => i.id === `proj-${proj.id}`);
                    const isSelected = idx === selectedIndex;
                    const statusCfg = STATUS_BADGES[proj.status] || STATUS_BADGES.draft;

                    return (
                      <button
                        key={proj.id}
                        onClick={() => handleSelect(flatItems[idx])}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        data-testid={`search-item-project-${proj.id}`}
                        className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all cursor-pointer ${
                          isSelected ? "bg-iris/15 text-cloud" : "text-ash hover:bg-white/5"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            isSelected ? "bg-iris/25 text-iris" : "bg-white/5 text-fog"
                          }`}>
                            <FolderOpen className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-cloud truncate">{proj.title}</p>
                            <p className="text-[11px] text-fog truncate">
                              {proj.client ? `${proj.client} · ` : ""}/{proj.slug || ""}
                            </p>
                          </div>
                        </div>
                        <span className={`text-[10px] font-medium border rounded px-1.5 py-0.5 ${statusCfg.color}`}>
                          {statusCfg.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer info strip */}
        <div className="p-3 border-t border-white/10 bg-obsidian flex items-center justify-between text-[11px] text-fog flex-shrink-0">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="font-mono bg-white/5 px-1 py-0.5 rounded border border-white/10">↑</kbd>
              <kbd className="font-mono bg-white/5 px-1 py-0.5 rounded border border-white/10">↓</kbd>
              to navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="font-mono bg-white/5 px-1 py-0.5 rounded border border-white/10">↵</kbd>
              to select
            </span>
          </div>
          <span className="font-mono text-[10px] text-fog/60">Navigatte Command Center</span>
        </div>
      </motion.div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(content, document.body);
};

export default GlobalAdminSearch;
