import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Search, Download, RefreshCw, ChevronUp, ChevronDown,
  Building2, Calendar, Inbox,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import LeadDrawer from "./LeadDrawer";
import api from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const STATUS_CONFIG = {
  new:       { label: "New",       color: "bg-iris/15 text-iris border-iris/25" },
  contacted: { label: "Contacted", color: "bg-signal/15 text-signal border-signal/25" },
  qualified: { label: "Qualified", color: "bg-periwinkle/15 text-periwinkle border-periwinkle/25" },
  converted: { label: "Converted", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" },
  closed:    { label: "Closed",    color: "bg-white/5 text-ash border-white/10" },
};

const TABS = [
  { value: "all",       label: "All" },
  { value: "new",       label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "qualified", label: "Qualified" },
  { value: "converted", label: "Converted" },
  { value: "closed",    label: "Closed" },
];

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function exportCsv(leads) {
  const headers = ["Name", "Email", "Phone", "Company", "Service Interest", "Status", "Message", "Submitted"];
  const rows = leads.map((l) => [
    l.name, l.email, l.phone ?? "", l.company ?? "",
    l.service_interest ?? "", l.status, l.message,
    formatDate(l.created_at),
  ].map((v) => `"${String(v).replace(/"/g, '""')}"`));
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `enquiries_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function SortIcon({ active, direction }) {
  if (!active) return <ChevronUp className="w-3 h-3 text-fog opacity-50" />;
  return direction === "asc"
    ? <ChevronUp className="w-3 h-3 text-iris" />
    : <ChevronDown className="w-3 h-3 text-iris" />;
}

const EnquiriesCRM = ({ initialTab = "all" }) => {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedLead, setSelectedLead] = useState(null);
  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const { toast } = useToast();
  const debounceRef = useRef(null);

  const fetchLeads = useCallback(async (tab, q, isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const params = {};
      if (tab !== "all") params.status = tab;
      if (q) params.search = q;
      const resp = await api.get("/admin/enquiries", { params });
      setLeads(resp.data);
    } catch {
      toast({ title: "Failed to load enquiries", variant: "destructive" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  // Debounce search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(searchInput), 350);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]);

  useEffect(() => {
    fetchLeads(activeTab, search);
  }, [fetchLeads, activeTab, search]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sortedLeads = useMemo(() => {
    return [...leads].sort((a, b) => {
      let va = a[sortKey] ?? "";
      let vb = b[sortKey] ?? "";
      if (typeof va === "string") va = va.toLowerCase();
      if (typeof vb === "string") vb = vb.toLowerCase();
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      if (va > vb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [leads, sortKey, sortDir]);

  const handleLeadUpdated = useCallback((updated) => {
    setLeads((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
    if (selectedLead?.id === updated.id) setSelectedLead(updated);
  }, [selectedLead]);

  const SortableHeader = ({ label, colKey, className = "" }) => (
    <button
      onClick={() => handleSort(colKey)}
      className={`flex items-center gap-1 text-xs text-fog hover:text-ash transition-colors ${className}`}
    >
      {label}
      <SortIcon active={sortKey === colKey} direction={sortDir} />
    </button>
  );

  return (
    <div className="space-y-5" data-testid="enquiries-crm">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fog" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search name, email, company…"
            className="bg-graphite/40 border-white/10 text-cloud text-sm pl-9 h-9 
                       placeholder:text-fog focus:border-iris/40"
            data-testid="enquiries-search"
          />
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchLeads(activeTab, search, true)}
            disabled={refreshing}
            className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 h-9 px-3 rounded-lg"
            data-testid="enquiries-refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => exportCsv(sortedLeads)}
            disabled={sortedLeads.length === 0}
            className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 h-9 px-3 rounded-lg"
            data-testid="enquiries-export-csv"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            CSV
          </Button>
        </div>
      </div>

      {/* Pipeline filter tabs */}
      <div className="flex items-center gap-1 overflow-x-auto pb-0.5 no-scrollbar">
        {TABS.map((tab) => {
          const count = tab.value === "all"
            ? leads.length
            : leads.filter((l) => l.status === tab.value).length;
          const isActive = activeTab === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              data-testid={`enquiries-tab-${tab.value}`}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium 
                          whitespace-nowrap transition-colors
                          ${isActive
                            ? "bg-iris/15 text-iris border border-iris/25"
                            : "text-fog hover:text-ash hover:bg-white/5 border border-transparent"}`}
            >
              {tab.label}
              <span className={`text-[11px] px-1.5 py-0.5 rounded-full 
                              ${isActive ? "bg-iris/20 text-iris" : "bg-white/5 text-fog"}`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div className="border border-white/10 rounded-feature overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[2fr_1.5fr_1fr_1fr] gap-4 px-4 py-3 
                        bg-graphite/30 border-b border-white/8 text-left">
          <SortableHeader label="Lead" colKey="name" />
          <SortableHeader label="Company" colKey="company" className="hidden sm:flex" />
          <SortableHeader label="Status" colKey="status" />
          <SortableHeader label="Submitted" colKey="created_at" className="hidden md:flex" />
        </div>

        {/* Rows */}
        {loading ? (
          <div className="py-16 flex flex-col items-center gap-3" data-testid="enquiries-loading">
            <RefreshCw className="w-5 h-5 text-fog animate-spin" />
            <span className="text-sm text-fog">Loading enquiries…</span>
          </div>
        ) : sortedLeads.length === 0 ? (
          <div className="py-16 flex flex-col items-center gap-3" data-testid="enquiries-empty">
            <Inbox className="w-8 h-8 text-fog" />
            <div className="text-center">
              <p className="text-sm text-ash">No leads found</p>
              <p className="text-xs text-fog mt-1">
                {search ? "Try a different search term." : "Enquiries will appear here once submitted."}
              </p>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {sortedLeads.map((lead) => {
              const cfg = STATUS_CONFIG[lead.status] ?? STATUS_CONFIG.new;
              return (
                <button
                  key={lead.id}
                  onClick={() => setSelectedLead(lead)}
                  data-testid={`enquiries-row-${lead.id}`}
                  className="w-full grid grid-cols-[2fr_1.5fr_1fr_1fr] gap-4 px-4 py-3.5 
                             text-left hover:bg-white/3 transition-colors group"
                >
                  {/* Name + email */}
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <p className="text-sm font-medium text-cloud group-hover:text-pure truncate transition-colors">
                        {lead.name}
                      </p>
                      {lead.scheduling_status === "booked" && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-mono bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                          <Calendar className="w-2.5 h-2.5" /> Booked
                        </span>
                      )}
                      {lead.is_test && (
                        <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25">
                          TEST
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-fog truncate mt-0.5">{lead.email}</p>
                  </div>

                  {/* Company */}
                  <div className="hidden sm:flex items-center gap-1.5 min-w-0">
                    {lead.company ? (
                      <>
                        <Building2 className="w-3.5 h-3.5 text-fog flex-shrink-0" />
                        <span className="text-sm text-ash truncate">{lead.company}</span>
                      </>
                    ) : (
                      <span className="text-sm text-fog">—</span>
                    )}
                  </div>

                  {/* Status */}
                  <div className="flex items-center">
                    <span className={`border rounded-lg px-2 py-0.5 text-[11px] font-medium ${cfg.color}`}>
                      {cfg.label}
                    </span>
                  </div>

                  {/* Date */}
                  <div className="hidden md:flex items-center gap-1.5">
                    <Calendar className="w-3 h-3 text-fog flex-shrink-0" />
                    <span className="text-xs text-fog">{formatDate(lead.created_at)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Lead count footer */}
      {!loading && sortedLeads.length > 0 && (
        <p className="text-xs text-fog text-center">
          Showing {sortedLeads.length} lead{sortedLeads.length !== 1 ? "s" : ""}
        </p>
      )}

      {/* Lead drawer */}
      <AnimatePresence>
        {selectedLead && (
          <LeadDrawer
            lead={selectedLead}
            onClose={() => setSelectedLead(null)}
            onLeadUpdated={handleLeadUpdated}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default EnquiriesCRM;
