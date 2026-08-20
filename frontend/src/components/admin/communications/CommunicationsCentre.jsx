import React, { useState, useEffect, useCallback } from "react";
import {
  Mail,
  Send,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Eye,
  RefreshCw,
  Search,
  Filter,
  Plus,
  Clock,
  Layers,
  FileText,
  Zap,
  Loader2,
  ExternalLink,
  ShieldCheck,
  Users,
  Ban,
  History,
  Play,
  Pause,
  StopCircle,
  BarChart2,
  FileCode,
  Sliders,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";

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
  const [activeTab, setActiveTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [outboxItems, setOutboxItems] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [audiences, setAudiences] = useState([]);
  const [suppressions, setSuppressions] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [testName, setTestName] = useState("");
  const [testTemplate, setTestTemplate] = useState("enquiry_acknowledgement");
  const [sendingTest, setSendingTest] = useState(false);

  // Detail Inspections
  const [selectedOutbox, setSelectedOutbox] = useState(null);
  const [retryingItem, setRetryingItem] = useState(false);
  const [selectedTemplateVersions, setSelectedTemplateVersions] = useState(null);
  const [launchChecklistModal, setLaunchChecklistModal] = useState(null);
  const [launchingCampaign, setLaunchingCampaign] = useState(false);

  // New Campaign Form Modal
  const [newCampaignModal, setNewCampaignModal] = useState(false);
  const [campName, setCampName] = useState("");
  const [campDesc, setCampDesc] = useState("");
  const [campEnv, setCampEnv] = useState("test");
  const [campSubject, setCampSubject] = useState("");
  const [campTpl, setCampTpl] = useState("enquiry_acknowledgement");
  const [campAudience, setCampAudience] = useState("");
  const [campTestRecipients, setCampTestRecipients] = useState("admin@navigatte.com");
  const [savingCampaign, setSavingCampaign] = useState(false);

  // Data Fetchers
  const fetchOverview = useCallback(async () => {
    try {
      const resp = await api.get("/admin/communications/overview");
      setOverview(resp.data);
    } catch (err) {
      console.error("Failed to load overview:", err);
    }
  }, []);

  const fetchDiagnostics = useCallback(async () => {
    try {
      const resp = await api.get("/admin/communications/diagnostics");
      setDiagnostics(resp.data);
    } catch (err) {
      console.error("Failed to load diagnostics:", err);
    }
  }, []);

  const fetchOutbox = useCallback(async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (searchQuery) params.search = searchQuery;
      const resp = await api.get("/admin/communications/outbox", { params });
      setOutboxItems(resp.data.items || []);
    } catch (err) {
      console.error("Failed to load outbox:", err);
    }
  }, [statusFilter, searchQuery]);

  const fetchTemplates = useCallback(async () => {
    try {
      const resp = await api.get("/admin/communications/templates");
      setTemplates(resp.data || []);
    } catch (err) {
      console.error("Failed to load templates:", err);
    }
  }, []);

  const fetchCampaigns = useCallback(async () => {
    try {
      const resp = await api.get("/admin/communications/campaigns");
      setCampaigns(resp.data.items || []);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    }
  }, []);

  const fetchAudiences = useCallback(async () => {
    try {
      const [audResp, supResp] = await Promise.all([
        api.get("/admin/communications/audiences"),
        api.get("/admin/communications/audiences/suppression"),
      ]);
      setAudiences(audResp.data.items || []);
      setSuppressions(supResp.data.items || []);
    } catch (err) {
      console.error("Failed to load audiences/suppressions:", err);
    }
  }, []);

  const fetchAnalyticsAndAudit = useCallback(async () => {
    try {
      const [anResp, auResp] = await Promise.all([
        api.get("/admin/communications/analytics"),
        api.get("/admin/communications/audit-logs"),
      ]);
      setAnalytics(anResp.data);
      setAuditLogs(auResp.data.items || []);
    } catch (err) {
      console.error("Failed to load analytics/audit:", err);
    }
  }, []);

  const reloadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      fetchOverview(),
      fetchDiagnostics(),
      fetchOutbox(),
      fetchTemplates(),
      fetchCampaigns(),
      fetchAudiences(),
      fetchAnalyticsAndAudit(),
    ]);
    setLoading(false);
  }, [fetchOverview, fetchDiagnostics, fetchOutbox, fetchTemplates, fetchCampaigns, fetchAudiences, fetchAnalyticsAndAudit]);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  // Actions
  const handleSendTest = async (e) => {
    e.preventDefault();
    if (!testEmail) {
      toast({ variant: "destructive", title: "Missing Email", description: "Provide a valid email address." });
      return;
    }

    setSendingTest(true);
    try {
      const resp = await api.post("/admin/communications/send-test", {
        recipient_email: testEmail,
        recipient_name: testName || "Test User",
        template_key: testTemplate,
        variables: {
          name: testName || "Test Recipient",
          service_interest: "Cloud Architecture Advisory",
          company: "Enterprise Corp",
          start_time: "Aug 25, 2026, 2:00 PM",
          timezone: "UTC",
          meeting_url: "https://navigatte.com/meet/test",
        },
      });

      if (resp.data.success) {
        toast({
          title: "Test Email Dispatched",
          description: `Dispatched '${testTemplate}' to ${testEmail} (Status: ${resp.data.status}).`,
        });
        setTestModalOpen(false);
        setTestEmail("");
        reloadAll();
      } else {
        toast({
          variant: "destructive",
          title: resp.data.status === "provider_disabled" ? "Provider Not Configured" : "Dispatch Failed",
          description: resp.data.error_message || `Delivery status: ${resp.data.status}`,
        });
        setTestModalOpen(false);
        reloadAll();
      }
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Dispatch Error",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setSendingTest(false);
    }
  };

  const handleRetryOutbox = async (outboxId) => {
    setRetryingItem(true);
    try {
      const resp = await api.post(`/admin/communications/outbox/${outboxId}/retry`);
      if (resp.data.success) {
        toast({
          title: "Retry Dispatched",
          description: `Message ${outboxId} sent (Attempt #${resp.data.attempt_count}).`,
        });
        setSelectedOutbox(null);
        reloadAll();
      } else {
        toast({
          variant: "destructive",
          title: "Retry Failed",
          description: resp.data.error_message || `Delivery status: ${resp.data.status}`,
        });
        reloadAll();
      }
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Retry Error",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setRetryingItem(false);
    }
  };

  const handleInspectVersions = async (key) => {
    try {
      const resp = await api.get(`/admin/communications/templates/${key}/versions`);
      setSelectedTemplateVersions({ key, versions: resp.data });
    } catch (err) {
      toast({ variant: "destructive", title: "Error", description: "Failed to load version history." });
    }
  };

  const handleInspectCampaignValidation = async (camp) => {
    try {
      const resp = await api.get(`/admin/communications/campaigns/${camp.id}/validate`);
      setLaunchChecklistModal({ campaign: camp, validation: resp.data });
    } catch (err) {
      toast({ variant: "destructive", title: "Error", description: err.response?.data?.detail || err.message });
    }
  };

  const handleLaunchCampaign = async (campaignId) => {
    setLaunchingCampaign(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${campaignId}/launch`);
      toast({
        title: "Campaign Launched",
        description: resp.data.message,
      });
      setLaunchChecklistModal(null);
      reloadAll();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Launch Failed",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setLaunchingCampaign(false);
    }
  };

  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    if (!campName || !campSubject) {
      toast({ variant: "destructive", title: "Missing Fields", description: "Please complete campaign details." });
      return;
    }
    setSavingCampaign(true);
    try {
      const rawRecipients = campTestRecipients
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean);

      await api.post("/admin/communications/campaigns", {
        name: campName,
        description: campDesc,
        environment: campEnv,
        subject: campSubject,
        template_key: campTpl,
        audience_id: campAudience || null,
        test_recipients: rawRecipients,
      });

      toast({ title: "Campaign Created", description: `Draft campaign '${campName}' saved.` });
      setNewCampaignModal(false);
      setCampName("");
      setCampDesc("");
      setCampSubject("");
      reloadAll();
    } catch (err) {
      toast({ variant: "destructive", title: "Creation Error", description: err.response?.data?.detail || err.message });
    } finally {
      setSavingCampaign(false);
    }
  };

  const metrics = overview?.metrics || {};
  const provider = overview?.provider || {};

  return (
    <div className="space-y-8" data-testid="communications-centre">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-display font-light text-cloud">
              Email Management System (EMS)
            </h1>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border bg-iris/15 text-iris border-iris/25">
              Control Plane
            </span>
            {diagnostics?.environment?.campaign_test_mode && (
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border bg-amber-500/15 text-amber-400 border-amber-500/25">
                Test Mode Active
              </span>
            )}
          </div>
          <p className="text-sm text-fog mt-1">
            Enterprise transactional engine, campaigns, audience suppression, and Resend telemetry.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            onClick={() => setTestModalOpen(true)}
            size="sm"
            className="bg-iris/80 hover:bg-iris text-white text-xs rounded-lg h-9"
          >
            <Send className="w-3.5 h-3.5 mr-1.5" />
            Send Test Email
          </Button>
          <Button
            onClick={() => setNewCampaignModal(true)}
            size="sm"
            variant="outline"
            className="border-white/10 text-cloud hover:bg-white/5 rounded-lg text-xs h-9"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            New Campaign
          </Button>
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

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Total Dispatches</span>
          <p className="text-2xl font-semibold text-cloud">{metrics.sent_count || 0}</p>
          <p className="text-[11px] text-fog font-mono">{metrics.total_outbox || 0} outbox records</p>
        </div>

        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Delivery Rate</span>
          <p className="text-2xl font-semibold text-emerald-400">{metrics.delivery_rate_percent || 100}%</p>
          <p className="text-[11px] text-fog font-mono">{metrics.delivered_count || 0} confirmed delivered</p>
        </div>

        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Open Rate</span>
          <p className="text-2xl font-semibold text-iris">{metrics.open_rate_percent || 0}%</p>
          <p className="text-[11px] text-fog font-mono">{metrics.opened_count || 0} opens tracked</p>
        </div>

        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Bounces & Suppressed</span>
          <p className="text-2xl font-semibold text-amber-400">{metrics.bounced_count || 0}</p>
          <p className="text-[11px] text-fog font-mono">{suppressions.length} global suppressions</p>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-px overflow-x-auto">
        {[
          { id: "overview", label: "Overview & Diagnostics", icon: Layers },
          { id: "outbox", label: "Transactional Outbox", icon: Mail },
          { id: "campaigns", label: `Campaigns (${campaigns.length})`, icon: Zap },
          { id: "templates", label: `Templates (${templates.length})`, icon: FileText },
          { id: "audiences", label: `Audiences & Suppression`, icon: Users },
          { id: "analytics", label: "Analytics & Audit Trail", icon: BarChart2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`comm-subtab-${tab.id}`}
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

      {/* Tab 1: Overview & Diagnostics */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="bg-obsidian border border-white/10 rounded-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-iris/15 text-iris border border-iris/20 flex items-center justify-center">
                  <Mail className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-cloud">Resend Communications Adapter</h3>
                  <p className="text-xs text-fog">Sending Domain: {provider.sending_domain}</p>
                </div>
              </div>
              <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${provider.configured ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" : "bg-amber-500/15 text-amber-400 border-amber-500/25"}`}>
                {provider.configured ? "Ready / Key Configured" : "Awaiting API Key"}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-xs">
              <div className="p-3 bg-white/5 rounded-xl space-y-1">
                <span className="text-fog">Default Sender</span>
                <p className="font-mono text-cloud">{provider.from_email}</p>
              </div>
              <div className="p-3 bg-white/5 rounded-xl space-y-1">
                <span className="text-fog">Inbound Webhook Endpoint</span>
                <p className="font-mono text-iris">{provider.webhook_endpoint}</p>
              </div>
              <div className="p-3 bg-white/5 rounded-xl space-y-1">
                <span className="text-fog">Signature Protection</span>
                <p className="font-mono text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Svix HMAC-SHA256
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Recent Outbox Dispatches</h3>
            <div className="bg-obsidian border border-white/10 rounded-xl overflow-hidden shadow-md">
              {outboxItems.length === 0 ? (
                <div className="p-8 text-center text-fog text-xs">No outbound emails recorded yet.</div>
              ) : (
                <div className="divide-y divide-white/5">
                  {outboxItems.slice(0, 5).map((item) => (
                    <div key={item.id} className="p-3.5 flex items-center justify-between gap-3 text-xs hover:bg-white/[0.02]">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase border ${STATUS_BADGES[item.status] || STATUS_BADGES.queued}`}>
                          {item.status}
                        </span>
                        <span className="font-medium text-cloud truncate">{item.subject}</span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 font-mono text-fog text-[11px]">
                        <span>{item.recipient_email}</span>
                        <span>{item.created_at ? new Date(item.created_at).toLocaleTimeString() : ""}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Outbox */}
      {activeTab === "outbox" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-obsidian border border-white/10 p-3 rounded-xl">
            <div className="relative w-full sm:w-72">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-fog" />
              <Input
                placeholder="Search recipient or subject..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-8 text-xs bg-white/5 border-white/10 text-cloud rounded-lg"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
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
                    {outboxItems.map((item) => (
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

      {/* Tab 3: Campaigns */}
      {activeTab === "campaigns" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {campaigns.map((camp) => (
              <div key={camp.id} className="bg-obsidian border border-white/10 rounded-xl p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-cloud">{camp.name}</h4>
                    <p className="text-xs text-fog mt-0.5">{camp.description || "No description provided."}</p>
                  </div>
                  <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${STATUS_BADGES[camp.status] || STATUS_BADGES.draft}`}>
                    {camp.status}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-fog">
                  <p><strong className="text-cloud">Subject:</strong> {camp.subject}</p>
                  <p><strong className="text-cloud">Template:</strong> {camp.template_key} (v{camp.template_version || 1})</p>
                  <p>
                    <strong className="text-cloud">Environment:</strong>{" "}
                    <span className={camp.environment === "production" ? "text-emerald-400 font-mono" : "text-amber-400 font-mono"}>
                      {camp.environment}
                    </span>
                  </p>
                  <p><strong className="text-cloud">Recipients:</strong> {camp.total_recipients || (camp.environment === "test" ? camp.test_recipients?.length : 0)} targets</p>
                </div>

                <div className="pt-2 border-t border-white/5 flex items-center justify-between gap-2">
                  <Button
                    onClick={() => handleInspectCampaignValidation(camp)}
                    size="sm"
                    variant="outline"
                    className="border-white/10 text-cloud hover:bg-white/5 text-xs h-7"
                  >
                    Checklist & Launch
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Templates */}
      {activeTab === "templates" && (
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

              <div className="space-y-1.5 text-xs text-fog">
                <p><strong className="text-cloud">Subject:</strong> {tpl.subject}</p>
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  <span className="text-[10px] uppercase font-mono text-fog/60">Variables:</span>
                  {tpl.variables?.map((v) => (
                    <span key={v} className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] font-mono text-cloud border border-white/10">
                      {`{{ ${v} }}`}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-2 border-t border-white/5 flex items-center justify-between">
                <button
                  onClick={() => handleInspectVersions(tpl.key)}
                  className="text-iris hover:underline text-xs flex items-center gap-1"
                >
                  <History className="w-3.5 h-3.5" /> Version History
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 5: Audiences & Suppression */}
      {activeTab === "audiences" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Audience Lists</h3>
            <div className="bg-obsidian border border-white/10 rounded-xl divide-y divide-white/5">
              {audiences.length === 0 ? (
                <div className="p-6 text-center text-fog text-xs">No audience groups defined.</div>
              ) : (
                audiences.map((aud) => (
                  <div key={aud.id} className="p-4 space-y-1">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-cloud">{aud.name}</h4>
                      <span className="text-xs font-mono text-iris">{aud.member_count} contacts</span>
                    </div>
                    <p className="text-xs text-fog">{aud.description}</p>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Global Suppression List</h3>
            <div className="bg-obsidian border border-white/10 rounded-xl divide-y divide-white/5 max-h-96 overflow-y-auto">
              {suppressions.length === 0 ? (
                <div className="p-6 text-center text-fog text-xs">Suppression list is empty.</div>
              ) : (
                suppressions.map((sup) => (
                  <div key={sup.id} className="p-3 flex items-center justify-between text-xs">
                    <span className="font-mono text-cloud">{sup.email}</span>
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

      {/* Tab 6: Analytics & Audit Trail */}
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

      {/* Outbox Detail Modal */}
      {selectedOutbox && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
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
                <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded text-rose-300 font-mono text-[11px]">
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

      {/* Launch Checklist Modal */}
      {launchChecklistModal && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud">Pre-Flight Launch Checklist</h3>
              <button onClick={() => setLaunchChecklistModal(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 bg-white/5 rounded">
                <span>Environment Match</span>
                <span className={launchChecklistModal.validation.checklist.environment_confirmed ? "text-emerald-400 font-mono" : "text-rose-400 font-mono"}>
                  {launchChecklistModal.validation.checklist.environment_confirmed ? "✓ Confirmed" : "✗ Mismatch"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 bg-white/5 rounded">
                <span>Provider Configured</span>
                <span className={launchChecklistModal.validation.checklist.provider_healthy ? "text-emerald-400 font-mono" : "text-rose-400 font-mono"}>
                  {launchChecklistModal.validation.checklist.provider_healthy ? "✓ Active" : "✗ Unconfigured"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 bg-white/5 rounded">
                <span>Target Recipients</span>
                <span className="font-mono text-iris">{launchChecklistModal.validation.checklist.target_recipients_count} targets</span>
              </div>
            </div>

            <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setLaunchChecklistModal(null)} className="border-white/10 text-ash text-xs h-8">
                Cancel
              </Button>
              <Button
                disabled={!launchChecklistModal.validation.is_valid || launchingCampaign}
                onClick={() => handleLaunchCampaign(launchChecklistModal.campaign.id)}
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8"
              >
                {launchingCampaign ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Play className="w-3.5 h-3.5 mr-1" />}
                Confirm & Launch
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* New Campaign Modal */}
      {newCampaignModal && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud">Create New Campaign</h3>
              <button onClick={() => setNewCampaignModal(false)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <form onSubmit={handleCreateCampaign} className="space-y-3 text-xs">
              <div>
                <label className="block text-fog mb-1">Campaign Name *</label>
                <Input
                  required
                  placeholder="Q3 Enterprise Advisory"
                  value={campName}
                  onChange={(e) => setCampName(e.target.value)}
                  className="bg-white/5 border-white/10 text-cloud text-xs"
                />
              </div>

              <div>
                <label className="block text-fog mb-1">Environment</label>
                <select
                  value={campEnv}
                  onChange={(e) => setCampEnv(e.target.value)}
                  className="w-full h-9 text-xs bg-white/5 border border-white/10 text-cloud rounded-lg px-2.5 outline-none"
                >
                  <option value="test" className="bg-[#101018]">Test (Restricted to Test Recipients)</option>
                  <option value="production" className="bg-[#101018]">Production (Audience Broadcast)</option>
                </select>
              </div>

              <div>
                <label className="block text-fog mb-1">Subject Line *</label>
                <Input
                  required
                  placeholder="Navigatte Technical Strategy Briefing"
                  value={campSubject}
                  onChange={(e) => setCampSubject(e.target.value)}
                  className="bg-white/5 border-white/10 text-cloud text-xs"
                />
              </div>

              {campEnv === "test" && (
                <div>
                  <label className="block text-fog mb-1">Test Recipients (Comma-separated)</label>
                  <Input
                    placeholder="qa@navigatte.com, admin@navigatte.com"
                    value={campTestRecipients}
                    onChange={(e) => setCampTestRecipients(e.target.value)}
                    className="bg-white/5 border-white/10 text-cloud text-xs"
                  />
                </div>
              )}

              <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setNewCampaignModal(false)} className="border-white/10 text-ash text-xs h-8">
                  Cancel
                </Button>
                <Button type="submit" disabled={savingCampaign} size="sm" className="bg-iris/80 hover:bg-iris text-white text-xs h-8">
                  {savingCampaign ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
                  Save Draft
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Send Test Email Modal */}
      {testModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud flex items-center gap-2">
                <Send className="w-4 h-4 text-iris" />
                Dispatch Test Email
              </h3>
              <button onClick={() => setTestModalOpen(false)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <form onSubmit={handleSendTest} className="space-y-3 text-xs">
              <div>
                <label className="block text-fog mb-1">Recipient Email *</label>
                <Input
                  type="email"
                  required
                  placeholder="admin@navigatte.com"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  className="bg-white/5 border-white/10 text-cloud text-xs"
                />
              </div>

              <div>
                <label className="block text-fog mb-1">Recipient Name</label>
                <Input
                  placeholder="Sarah Connor"
                  value={testName}
                  onChange={(e) => setTestName(e.target.value)}
                  className="bg-white/5 border-white/10 text-cloud text-xs"
                />
              </div>

              <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setTestModalOpen(false)} className="border-white/10 text-ash text-xs h-8">
                  Cancel
                </Button>
                <Button type="submit" disabled={sendingTest} size="sm" className="bg-iris/80 hover:bg-iris text-white text-xs h-8">
                  {sendingTest ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Send className="w-3.5 h-3.5 mr-1" />}
                  Dispatch Email
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CommunicationsCentre;
