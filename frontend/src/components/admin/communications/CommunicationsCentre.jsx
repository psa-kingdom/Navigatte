/**
 * Communications Centre (Campaign Studio & Email Dispatch Control)
 *
 * Integrated administration interface for email campaigns, transactional outbox,
 * template lifecycle, audience management, suppressions, and delivery telemetry.
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Mail,
  Send,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Eye,
  RefreshCw,
  Search,
  Plus,
  Clock,
  Layers,
  FileText,
  Zap,
  Loader2,
  ShieldCheck,
  Users,
  Ban,
  History,
  Play,
  Pause,
  BarChart2,
  FileCode,
  Smartphone,
  Monitor,
  Copy,
  Trash2,
  Edit3,
  Upload,
  Check,
  Sparkles,
  FileSpreadsheet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";
import { CampaignStudio } from "./CampaignStudio";

const STATUS_BADGES = {
  sent: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  delivered: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  opened: "bg-iris/15 text-iris border-iris/25",
  clicked: "bg-purple-500/15 text-purple-400 border-purple-500/25",
  bounced: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  failed: "bg-rose-500/15 text-rose-400 border-rose-500/25",
  queued: "bg-white/5 text-fog border-white/10",
  sending: "bg-white/10 text-cloud border-white/20",
  provider_disabled: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  draft: "bg-white/5 text-fog border-white/10",
  ready: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  scheduled: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  paused: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  cancelled: "bg-rose-500/15 text-rose-400 border-rose-500/25",
  completed: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
};

export const CommunicationsCentre = () => {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("composer"); // 'composer' | 'campaigns' | 'templates' | 'audiences' | 'outbox' | 'analytics'
  const [loading, setLoading] = useState(true);

  // System Diagnostics & State
  const [overview, setOverview] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [audiences, setAudiences] = useState([]);
  const [suppressions, setSuppressions] = useState([]);
  const [outboxItems, setOutboxItems] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [analytics, setAnalytics] = useState(null);

  // Campaign Studio Active State
  const [activeCampaignForComposer, setActiveCampaignForComposer] = useState(null);

  // Modals & Inspectors
  const [selectedOutbox, setSelectedOutbox] = useState(null);
  const [retryingItem, setRetryingItem] = useState(false);
  const [selectedTemplateVersions, setSelectedTemplateVersions] = useState(null);
  const [previewingVersion, setPreviewingVersion] = useState(null);
  const [importModal, setImportModal] = useState(null);
  const [importMode, setImportMode] = useState("file"); // 'file' | 'paste'
  const [csvImportText, setCsvImportText] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [csvImportResult, setCsvImportResult] = useState(null);
  const [importingData, setImportingData] = useState(false);
  const [outboxSearchQuery, setOutboxSearchQuery] = useState("");
  const [outboxStatusFilter, setOutboxStatusFilter] = useState("");
  const fileInputRef = useRef(null);

  // Data Fetching
  const reloadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [
        ovResp,
        diagResp,
        tplResp,
        campResp,
        audResp,
        supResp,
        outResp,
        auResp,
        anResp,
      ] = await Promise.allSettled([
        api.get("/admin/communications/overview"),
        api.get("/admin/communications/diagnostics"),
        api.get("/admin/communications/templates"),
        api.get("/admin/communications/campaigns"),
        api.get("/admin/communications/audiences"),
        api.get("/admin/communications/audiences/suppression"),
        api.get("/admin/communications/outbox"),
        api.get("/admin/communications/audit-logs"),
        api.get("/admin/communications/analytics"),
      ]);

      if (ovResp.status === "fulfilled") setOverview(ovResp.value.data);
      if (diagResp.status === "fulfilled") setDiagnostics(diagResp.value.data);
      if (tplResp.status === "fulfilled") setTemplates(tplResp.value.data || []);
      if (campResp.status === "fulfilled") setCampaigns(campResp.value.data?.items || []);
      if (audResp.status === "fulfilled") setAudiences(audResp.value.data?.items || []);
      if (supResp.status === "fulfilled") setSuppressions(supResp.value.data?.items || []);
      if (outResp.status === "fulfilled") setOutboxItems(outResp.value.data?.items || []);
      if (auResp.status === "fulfilled") setAuditLogs(auResp.value.data?.items || []);
      if (anResp.status === "fulfilled") setAnalytics(anResp.value.data);
    } catch (err) {
      console.error("Communications reload error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  // Retry Single Outbox Item
  const handleRetryOutbox = async (outboxId) => {
    setRetryingItem(true);
    try {
      const resp = await api.post(`/admin/communications/outbox/${outboxId}/retry`);
      if (resp.data.success) {
        toast({ title: "Retry Dispatched", description: `Message ${outboxId} dispatched successfully.` });
        setSelectedOutbox(null);
        reloadAll();
      } else {
        toast({ variant: "destructive", title: "Retry Failed", description: resp.data.error_message || resp.data.status });
      }
    } catch (err) {
      toast({ variant: "destructive", title: "Retry Error", description: err.response?.data?.detail || err.message });
    } finally {
      setRetryingItem(false);
    }
  };

  // Audience Import Execution (File or Paste)
  const handleExecuteImport = async (audienceId) => {
    if (importMode === "file") {
      if (!selectedFile) {
        toast({ variant: "destructive", title: "No file selected", description: "Please choose a CSV or XLSX file." });
        return;
      }
      setImportingData(true);
      try {
        const formData = new FormData();
        formData.append("file", selectedFile);
        const resp = await api.post(`/admin/communications/audiences/${audienceId}/import-file`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setCsvImportResult(resp.data);
        toast({
          title: "File Import Complete",
          description: `Imported ${resp.data.imported_count} contacts (${resp.data.suppressed_count} auto-suppressed).`,
        });
        reloadAll();
      } catch (err) {
        toast({ variant: "destructive", title: "Import Failed", description: err.response?.data?.detail || err.message });
      } finally {
        setImportingData(false);
      }
    } else {
      // Paste mode
      if (!csvImportText.trim()) {
        toast({ variant: "destructive", title: "Empty Data", description: "Paste CSV or contact records to import." });
        return;
      }
      setImportingData(true);
      try {
        const lines = csvImportText.split("\n").map((l) => l.trim()).filter(Boolean);
        const contacts = lines.map((line) => {
          const parts = line.split(",").map((p) => p.trim());
          return { email: parts[0], name: parts[1] || "", company: parts[2] || "" };
        });
        const resp = await api.post(`/admin/communications/audiences/${audienceId}/import`, { contacts });
        setCsvImportResult(resp.data);
        toast({
          title: "Import Complete",
          description: `Imported ${resp.data.imported_count} contacts (${resp.data.suppressed_count} auto-suppressed).`,
        });
        reloadAll();
      } catch (err) {
        toast({ variant: "destructive", title: "Import Failed", description: err.response?.data?.detail || err.message });
      } finally {
        setImportingData(false);
      }
    }
  };

  const isProduction = diagnostics?.environment?.current === "production";
  const isWorkerRunning = diagnostics?.worker?.status === "running";

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-iris/20 border border-iris/40 flex items-center justify-center text-iris">
              <Mail className="w-4 h-4" />
            </div>
            <h1 className="text-xl font-semibold text-cloud tracking-tight">Communications Centre</h1>
          </div>
          <p className="text-xs text-fog mt-1">
            Campaign Studio, transactional email engine, durable delivery outbox, and audience suppression controls.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={reloadAll}
            disabled={loading}
            variant="outline"
            size="sm"
            className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 rounded-lg text-xs h-9"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Safety Layer Banner */}
      <div className={`border rounded-xl p-4 space-y-2 ${
        isProduction
          ? "bg-rose-950/20 border-rose-500/25 text-rose-300"
          : "bg-emerald-950/20 border-emerald-500/25 text-emerald-300"
      }`}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider font-mono">
            <ShieldCheck className="w-4 h-4" />
            {isProduction ? "PRODUCTION ENVIRONMENT ACTIVE" : "TEST MODE ACTIVE (Safety Boundaries Enforced)"}
          </div>
          <span className="text-[11px] font-mono opacity-80">
            {isProduction
              ? "Live sending enabled — 2-step verification and recipient count confirmation enforced."
              : "Campaigns in test mode dispatch strictly to configured test recipients."}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-fog font-mono">
          <div>
            Provider: <strong className="text-cloud">{diagnostics?.provider?.name || "Resend"}</strong>
            {diagnostics?.provider?.has_api_key ? (
              <span className="text-emerald-400 ml-1.5 font-bold">✓ Ready</span>
            ) : (
              <span className="text-amber-400 ml-1.5 font-bold">⚠ API Key Unset</span>
            )}
          </div>
          <div>
            From: <span className="text-cloud">{diagnostics?.provider?.from_email || "Navigatte <updates@updates.navigatte.com>"}</span>
          </div>
          <div>
            Delivery Worker:{" "}
            <span className={isWorkerRunning ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
              {isWorkerRunning ? "✓ Active (Lifespan Daemon)" : "Stopped"}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-px overflow-x-auto">
        {[
          { id: "composer", label: "Campaign Studio", icon: Send },
          { id: "campaigns", label: `Campaigns (${campaigns.length})`, icon: Zap },
          { id: "templates", label: `Templates (${templates.length})`, icon: FileText },
          { id: "audiences", label: `Audiences & Suppression`, icon: Users },
          { id: "outbox", label: `Transactional Outbox (${outboxItems.length})`, icon: Mail },
          { id: "analytics", label: "Analytics & Audit Logs", icon: BarChart2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`comm-tab-${tab.id}`}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium rounded-t-lg transition-all whitespace-nowrap border-b-2 -mb-px ${
                isActive
                  ? "border-iris text-cloud bg-white/[0.04]"
                  : "border-transparent text-ash hover:text-cloud hover:bg-white/[0.02]"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? "text-iris" : "text-fog"}`} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: CAMPAIGN STUDIO (One-Screen Studio Component) */}
      {/* ========================================================================= */}
      {activeTab === "composer" && (
        <CampaignStudio
          templates={templates}
          audiences={audiences}
          suppressions={suppressions}
          diagnostics={diagnostics}
          initialCampaign={activeCampaignForComposer}
          onCampaignSaved={(id) => reloadAll()}
          onCampaignLaunched={(id) => {
            reloadAll();
            setActiveTab("campaigns");
          }}
        />
      )}

      {/* ========================================================================= */}
      {/* TAB 2: CAMPAIGNS LIST */}
      {/* ========================================================================= */}
      {activeTab === "campaigns" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Registered Campaigns ({campaigns.length})</h3>
            <Button
              size="sm"
              onClick={() => {
                setActiveCampaignForComposer(null);
                setActiveTab("composer");
              }}
              className="bg-iris text-white text-xs h-8"
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> New Campaign
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {campaigns.map((camp) => (
              <div key={camp.id} className="bg-obsidian border border-white/10 rounded-xl p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-cloud">{camp.name}</h4>
                    <p className="text-xs text-fog mt-0.5">{camp.subject}</p>
                  </div>
                  <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${STATUS_BADGES[camp.status] || STATUS_BADGES.draft}`}>
                    {camp.status}
                  </span>
                </div>

                <div className="space-y-1 text-xs text-fog">
                  <p><strong className="text-cloud">Environment:</strong> <span className={camp.environment === "production" ? "text-emerald-400 font-mono" : "text-amber-400 font-mono"}>{camp.environment}</span></p>
                  <p><strong className="text-cloud">Recipients:</strong> {camp.total_recipients || 0} targets</p>
                  <p><strong className="text-cloud">Template:</strong> {camp.template_key} {camp.template_version ? `(v${camp.template_version})` : ""}</p>
                </div>

                <div className="pt-2 border-t border-white/5 flex items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      setActiveCampaignForComposer(camp);
                      setActiveTab("composer");
                    }}
                    className="text-iris hover:underline text-xs font-medium"
                  >
                    Open in Campaign Studio →
                  </button>
                  <span className="text-[10px] font-mono text-fog">
                    {camp.created_at ? new Date(camp.created_at).toLocaleDateString() : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: TEMPLATES & VERSIONS */}
      {/* ========================================================================= */}
      {activeTab === "templates" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">System & Custom Templates ({templates.length})</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {templates.map((tpl) => (
              <div key={tpl.id} className="bg-obsidian border border-white/10 rounded-xl p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-cloud">{tpl.name}</h4>
                    <div className="flex items-center gap-2 mt-0.5">
                      <p className="text-[11px] font-mono text-iris">{tpl.key}</p>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-fog border border-white/10">
                        v{tpl.version || 1}
                      </span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                    {tpl.category || "transactional"}
                  </span>
                </div>

                <p className="text-xs text-fog"><strong className="text-cloud">Subject:</strong> {tpl.subject}</p>

                <div className="pt-2 border-t border-white/5 flex items-center justify-between">
                  <button
                    onClick={() => {
                      setActiveCampaignForComposer({
                        name: `Campaign using ${tpl.name}`,
                        template_key: tpl.key,
                        subject: tpl.subject,
                        custom_html: tpl.body_html,
                      });
                      setActiveTab("composer");
                    }}
                    className="text-iris hover:underline text-xs"
                  >
                    Compose with Template
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        const resp = await api.get(`/admin/communications/templates/${tpl.key}/versions`);
                        setSelectedTemplateVersions({ key: tpl.key, versions: resp.data });
                      } catch (err) {
                        toast({ variant: "destructive", title: "Error", description: "Failed to load versions" });
                      }
                    }}
                    className="text-fog hover:text-cloud text-xs flex items-center gap-1"
                  >
                    <History className="w-3.5 h-3.5" /> Version History
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: AUDIENCES & SUPPRESSION */}
      {/* ========================================================================= */}
      {activeTab === "audiences" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Audience Lists */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Audience Lists</h3>
            </div>
            <div className="bg-obsidian border border-white/10 rounded-xl divide-y divide-white/5">
              {audiences.length === 0 ? (
                <div className="p-6 text-center text-fog text-xs">No audience groups defined.</div>
              ) : (
                audiences.map((aud) => (
                  <div key={aud.id} className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-cloud">{aud.name}</h4>
                      <span className="text-xs font-mono text-iris font-semibold">{aud.member_count} contacts</span>
                    </div>
                    <p className="text-xs text-fog">{aud.description || "No description."}</p>
                    <div className="pt-1 flex items-center gap-2">
                      <Button
                        onClick={() => {
                          setImportModal(aud);
                          setImportMode("file");
                          setSelectedFile(null);
                          setCsvImportText("");
                          setCsvImportResult(null);
                        }}
                        size="sm"
                        variant="outline"
                        className="border-white/10 text-cloud hover:bg-white/5 text-[11px] h-7"
                      >
                        <Upload className="w-3 h-3 mr-1" /> Import CSV / XLSX
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Global Suppression List */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Global Suppression List ({suppressions.length})</h3>
            </div>
            <div className="bg-obsidian border border-white/10 rounded-xl divide-y divide-white/5 max-h-[400px] overflow-y-auto">
              {suppressions.length === 0 ? (
                <div className="p-6 text-center text-fog text-xs">Suppression list is empty.</div>
              ) : (
                suppressions.map((sup) => (
                  <div key={sup.id} className="p-3 flex items-center justify-between text-xs">
                    <div>
                      <p className="font-mono text-cloud">{sup.email}</p>
                      <p className="text-[10px] text-fog">{sup.source || "system"}</p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase border bg-amber-500/15 text-amber-400 border-amber-500/25">
                      {sup.reason}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 5: TRANSACTIONAL OUTBOX */}
      {/* ========================================================================= */}
      {activeTab === "outbox" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-obsidian border border-white/10 p-3 rounded-xl">
            <div className="relative w-full sm:w-72">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-fog" />
              <Input
                placeholder="Search recipient or subject..."
                value={outboxSearchQuery}
                onChange={(e) => setOutboxSearchQuery(e.target.value)}
                className="pl-9 h-8 text-xs bg-white/5 border-white/10 text-cloud rounded-lg"
              />
            </div>

            <select
              value={outboxStatusFilter}
              onChange={(e) => setOutboxStatusFilter(e.target.value)}
              className="h-8 text-xs bg-white/5 border border-white/10 text-cloud rounded-lg px-2.5 outline-none"
            >
              <option value="" className="bg-[#101018]">All Statuses</option>
              <option value="sent" className="bg-[#101018]">Sent</option>
              <option value="delivered" className="bg-[#101018]">Delivered</option>
              <option value="opened" className="bg-[#101018]">Opened</option>
              <option value="bounced" className="bg-[#101018]">Bounced</option>
              <option value="failed" className="bg-[#101018]">Failed</option>
              <option value="provider_disabled" className="bg-[#101018]">Provider Disabled</option>
            </select>
          </div>

          <div className="bg-obsidian border border-white/10 rounded-xl overflow-hidden shadow-md">
            {outboxItems.length === 0 ? (
              <div className="p-12 text-center text-fog text-xs">No matching emails found in outbox.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/10 text-fog font-mono uppercase text-[11px] bg-white/[0.02]">
                    <tr>
                      <th className="p-3">Status</th>
                      <th className="p-3">Recipient</th>
                      <th className="p-3">Subject</th>
                      <th className="p-3">Template</th>
                      <th className="p-3">Environment</th>
                      <th className="p-3">Dispatched</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-ash">
                    {outboxItems
                      .filter((item) => !outboxStatusFilter || item.status === outboxStatusFilter)
                      .filter(
                        (item) =>
                          !outboxSearchQuery ||
                          item.recipient_email?.toLowerCase().includes(outboxSearchQuery.toLowerCase()) ||
                          item.subject?.toLowerCase().includes(outboxSearchQuery.toLowerCase())
                      )
                      .map((item) => (
                        <tr key={item.id} className="hover:bg-white/[0.02] transition-colors">
                          <td className="p-3">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase border ${STATUS_BADGES[item.status] || STATUS_BADGES.queued}`}>
                              {item.status}
                            </span>
                          </td>
                          <td className="p-3 font-mono text-cloud">{item.recipient_email}</td>
                          <td className="p-3 font-medium text-cloud truncate max-w-xs">{item.subject}</td>
                          <td className="p-3 font-mono text-fog text-[11px]">{item.template_key || "custom"}</td>
                          <td className="p-3 font-mono text-[11px]">
                            <span className={item.environment === "production" ? "text-emerald-400" : "text-amber-400"}>
                              {item.environment || "test"}
                            </span>
                          </td>
                          <td className="p-3 font-mono text-fog text-[11px]">
                            {item.created_at ? new Date(item.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—"}
                          </td>
                          <td className="p-3 text-right">
                            <button
                              onClick={() => setSelectedOutbox(item)}
                              className="text-iris hover:underline text-[11px] font-medium"
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 6: ANALYTICS & AUDIT LOGS */}
      {/* ========================================================================= */}
      {activeTab === "analytics" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
              <span className="text-xs text-fog uppercase font-mono">Delivered</span>
              <p className="text-xl font-semibold text-emerald-400">{analytics?.totals?.delivered || 0}</p>
            </div>
            <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
              <span className="text-xs text-fog uppercase font-mono">Open Rate</span>
              <p className="text-xl font-semibold text-iris">{analytics?.rates?.open_rate_percent || 0}%</p>
            </div>
            <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
              <span className="text-xs text-fog uppercase font-mono">Click Rate</span>
              <p className="text-xl font-semibold text-purple-400">{analytics?.rates?.click_rate_percent || 0}%</p>
            </div>
            <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
              <span className="text-xs text-fog uppercase font-mono">Bounce Rate</span>
              <p className="text-xl font-semibold text-amber-400">{analytics?.rates?.bounce_rate_percent || 0}%</p>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Administrative Audit Trail</h3>
            <div className="bg-obsidian border border-white/10 rounded-xl overflow-hidden divide-y divide-white/5">
              {auditLogs.length === 0 ? (
                <div className="p-6 text-center text-fog text-xs">No audit events recorded yet.</div>
              ) : (
                auditLogs.map((log) => (
                  <div key={log.id} className="p-3.5 flex items-center justify-between text-xs hover:bg-white/[0.02]">
                    <div className="space-y-0.5">
                      <p className="font-mono text-cloud font-medium">{log.action}</p>
                      <p className="text-fog text-[11px]">Actor: {log.actor_email} • Target: {log.target_type} ({log.target_id})</p>
                    </div>
                    <span className="text-[11px] font-mono text-fog">
                      {log.created_at ? new Date(log.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : ""}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS */}
      {/* ========================================================================= */}

      {/* CSV / XLSX Import Modal */}
      {importModal && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-medium text-cloud">Import Contacts into {importModal.name}</h3>
                <p className="text-xs text-fog mt-0.5">Supports CSV and Excel (.xlsx) formats.</p>
              </div>
              <button onClick={() => setImportModal(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            {/* Mode toggle: File Upload vs Text Paste */}
            <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-lg">
              <button
                type="button"
                onClick={() => setImportMode("file")}
                className={`py-1.5 text-xs font-medium rounded-md transition-all ${
                  importMode === "file" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                }`}
              >
                Upload CSV / XLSX File
              </button>
              <button
                type="button"
                onClick={() => setImportMode("paste")}
                className={`py-1.5 text-xs font-medium rounded-md transition-all ${
                  importMode === "paste" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                }`}
              >
                Paste Contact Rows
              </button>
            </div>

            {importMode === "file" ? (
              <div className="space-y-3">
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-white/15 hover:border-iris/50 rounded-xl p-6 text-center cursor-pointer transition-all bg-white/[0.02]"
                >
                  <FileSpreadsheet className="w-8 h-8 text-iris mx-auto mb-2 opacity-80" />
                  {selectedFile ? (
                    <div>
                      <p className="text-xs text-cloud font-medium font-mono">{selectedFile.name}</p>
                      <p className="text-[10px] text-fog mt-0.5">{(selectedFile.size / 1024).toFixed(1)} KB • Click to choose another</p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-xs text-cloud font-medium">Click to select CSV or XLSX file</p>
                      <p className="text-[10px] text-fog mt-0.5">Columns required: email (name, company optional)</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-xs">
                <label className="block text-fog">Paste CSV Rows (Format: <code>email, name, company</code>)</label>
                <textarea
                  rows={8}
                  value={csvImportText}
                  onChange={(e) => setCsvImportText(e.target.value)}
                  placeholder={`john@acme.com, John Doe, Acme Corp\nalice@advisory.io, Alice Smith, Advisory LLC`}
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2.5 text-xs text-cloud font-mono outline-none focus:border-iris resize-y"
                />
              </div>
            )}

            {csvImportResult && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/25 rounded text-xs text-emerald-300 space-y-1 font-mono">
                <p>Total Rows: {csvImportResult.total_rows}</p>
                <p>Imported: {csvImportResult.imported_count}</p>
                <p>Auto-Suppressed: {csvImportResult.suppressed_count}</p>
                <p>Duplicates / Invalid: {csvImportResult.duplicate_count + csvImportResult.invalid_count}</p>
              </div>
            )}

            <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setImportModal(null)} className="border-white/10 text-ash text-xs h-8">
                Close
              </Button>
              <Button
                disabled={importingData || (importMode === "file" && !selectedFile) || (importMode === "paste" && !csvImportText.trim())}
                onClick={() => handleExecuteImport(importModal.id)}
                size="sm"
                className="bg-iris text-white text-xs h-8"
              >
                {importingData ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Upload className="w-3.5 h-3.5 mr-1" />}
                Run Import
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Outbox Detail Modal */}
      {selectedOutbox && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud truncate">{selectedOutbox.subject}</h3>
              <button onClick={() => setSelectedOutbox(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <div className="space-y-2 text-xs text-ash">
              <div className="flex items-center justify-between">
                <span className="text-fog">Recipient:</span>
                <span className="font-mono text-cloud">{selectedOutbox.recipient_email}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Status:</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase border ${STATUS_BADGES[selectedOutbox.status]}`}>
                  {selectedOutbox.status}
                </span>
              </div>
              {selectedOutbox.provider_message_id && (
                <div className="flex items-center justify-between">
                  <span className="text-fog">Provider Message ID:</span>
                  <span className="font-mono text-[11px] text-iris">{selectedOutbox.provider_message_id}</span>
                </div>
              )}
              {selectedOutbox.error_message && (
                <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 rounded text-rose-300 font-mono text-[11px]">
                  <p className="font-semibold text-[10px] uppercase text-rose-400">Failure Reason:</p>
                  <p className="mt-0.5">{selectedOutbox.error_message}</p>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              {["failed", "provider_disabled", "queued", "sending"].includes(selectedOutbox.status) && (
                <Button
                  onClick={() => handleRetryOutbox(selectedOutbox.id)}
                  disabled={retryingItem}
                  size="sm"
                  className="bg-iris/80 hover:bg-iris text-white text-xs h-8"
                >
                  {retryingItem ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <RefreshCw className="w-3.5 h-3.5 mr-1" />}
                  Retry Dispatch
                </Button>
              )}
              <div className="flex-1" />
              <Button variant="outline" size="sm" onClick={() => setSelectedOutbox(null)} className="border-white/10 text-ash text-xs h-8">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Version History Modal */}
      {selectedTemplateVersions && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud">Version History: {selectedTemplateVersions.key}</h3>
              <button onClick={() => setSelectedTemplateVersions(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <div className="space-y-2 max-h-72 overflow-y-auto">
              {selectedTemplateVersions.versions.map((v) => (
                <div key={v.id} className="p-3 bg-white/5 rounded-lg flex items-center justify-between text-xs">
                  <div>
                    <span className="font-mono text-iris font-semibold">Version {v.version}</span>
                    <p className="text-[11px] text-cloud mt-0.5">{v.subject}</p>
                    <p className="text-[10px] text-fog">{v.change_summary || "Updated"}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        try {
                          const resp = await api.get(`/admin/communications/templates/${selectedTemplateVersions.key}/versions/${v.version}/preview`);
                          setPreviewingVersion(resp.data);
                        } catch (err) {
                          toast({ variant: "destructive", title: "Preview Failed", description: "Could not load preview." });
                        }
                      }}
                      className="border-white/10 text-fog hover:text-cloud text-xs h-7 px-2"
                    >
                      Preview
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        try {
                          await api.post(`/admin/communications/templates/${selectedTemplateVersions.key}/restore/${v.version}`);
                          toast({ title: "Template Restored", description: `Restored to version ${v.version}` });
                          setSelectedTemplateVersions(null);
                          reloadAll();
                        } catch (err) {
                          toast({ variant: "destructive", title: "Error", description: "Failed to restore version" });
                        }
                      }}
                      className="border-white/10 text-cloud text-xs h-7 px-2"
                    >
                      Restore
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-end">
              <Button onClick={() => setSelectedTemplateVersions(null)} className="border-white/10 text-ash text-xs h-8">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Version Preview Modal */}
      {previewingVersion && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-medium text-cloud">
                  Preview: {previewingVersion.name} (v{previewingVersion.version})
                </h3>
                <p className="text-xs text-fog font-mono mt-0.5">Subject: {previewingVersion.subject}</p>
              </div>
              <button onClick={() => setPreviewingVersion(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <div className="border border-white/10 rounded-xl overflow-hidden bg-white shadow-inner">
              <iframe
                srcDoc={previewingVersion.html_body}
                title="Version preview"
                sandbox="allow-same-origin"
                className="w-full border-0"
                style={{ height: "340px" }}
              />
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-end">
              <Button onClick={() => setPreviewingVersion(null)} className="border-white/10 text-ash text-xs h-8">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CommunicationsCentre;
