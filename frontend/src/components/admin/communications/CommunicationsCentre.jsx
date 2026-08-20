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
  Smartphone,
  Monitor,
  Copy,
  Trash2,
  Edit3,
  Upload,
  Check,
  ArrowRight,
  Sparkles,
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

const PLACEHOLDERS = [
  { label: "{{name}}", desc: "Recipient full name" },
  { label: "{{company}}", desc: "Company / organization" },
  { label: "{{email}}", desc: "Recipient email" },
  { label: "{{service_interest}}", desc: "Consulting interest" },
  { label: "{{start_time}}", desc: "Scheduled meeting date/time" },
  { label: "{{meeting_url}}", desc: "Cal.com / video link" },
  { label: "{{unsubscribe_url}}", desc: "Direct opt-out URL" },
];

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

  // Global Configured Test Recipient
  const [testRecipient, setTestRecipient] = useState("ishanchauhan2001@gmail.com");
  const [editingTestRecipient, setEditingTestRecipient] = useState(false);
  const [testRecipientInput, setTestRecipientInput] = useState("ishanchauhan2001@gmail.com");

  // Campaign Composer State
  const [sendMode, setSendMode] = useState("test"); // 'test' | 'production'
  const [campTitle, setCampTitle] = useState("");
  const [audienceSource, setAudienceSource] = useState("both"); // 'newsletter' | 'manual' | 'both' | 'audience'
  const [selectedAudienceId, setSelectedAudienceId] = useState("");
  const [manualRecipientsText, setManualRecipientsText] = useState("");
  const [exclusionsList, setExclusionsList] = useState(["@navigatte.com"]);
  const [exclusionsModalOpen, setExclusionsModalOpen] = useState(false);
  const [newExclusionInput, setNewExclusionInput] = useState("");

  // Email Content Composition State
  const [selectedTemplateKey, setSelectedTemplateKey] = useState("custom");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailHtml, setEmailHtml] = useState(
    `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1e293b; line-height: 1.6;">
  <h2 style="color: #0f172a;">Navigatte Advisory & Strategy Briefing</h2>
  <p>Hello {{name}},</p>
  <p>We are pleased to share our latest architecture and engineering advisory update.</p>
  <p>If you have questions regarding your project roadmap at {{company}}, let us know.</p>
  <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
  <p style="font-size: 12px; color: #64748b;">Navigatte Strategy & Engineering • <a href="{{unsubscribe_url}}" style="color: #6366f1;">Unsubscribe</a></p>
</div>`
  );
  const [previewViewport, setPreviewViewport] = useState("desktop"); // 'desktop' | 'mobile'

  // Composer Actions State
  const [sendingTestFromComposer, setSendingTestFromComposer] = useState(false);
  const [savingCampaignDraft, setSavingCampaignDraft] = useState(false);
  const [currentCampaignId, setCurrentCampaignId] = useState(null);
  const [launchChecklistModal, setLaunchChecklistModal] = useState(null);
  const [launchingCampaign, setLaunchingCampaign] = useState(false);

  // Modals & Inspectors
  const [selectedOutbox, setSelectedOutbox] = useState(null);
  const [retryingItem, setRetryingItem] = useState(false);
  const [templateEditorModal, setTemplateEditorModal] = useState(null);
  const [selectedTemplateVersions, setSelectedTemplateVersions] = useState(null);
  const [csvImportModal, setCsvImportModal] = useState(null);
  const [csvImportText, setCsvImportText] = useState("");
  const [csvImportResult, setCsvImportResult] = useState(null);
  const [importingCsv, setImportingCsv] = useState(false);
  const [outboxSearchQuery, setOutboxSearchQuery] = useState("");
  const [outboxStatusFilter, setOutboxStatusFilter] = useState("");

  const textareaRef = useRef(null);

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
      if (diagResp.status === "fulfilled") {
        setDiagnostics(diagResp.value.data);
        const configuredRecipients = diagResp.value.data?.environment?.allowed_test_recipients;
        if (configuredRecipients && configuredRecipients.length > 0) {
          setTestRecipient(configuredRecipients[0]);
          setTestRecipientInput(configuredRecipients[0]);
        }
      }
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

  // Real-Time Net Recipient Calculation
  const calculateAudienceBreakdown = () => {
    if (sendMode === "test") {
      return { raw: 1, suppressed: 0, excluded: 0, final: 1 };
    }

    let manualEmails = manualRecipientsText
      .split(/[\n,;]/)
      .map((e) => e.trim().toLowerCase())
      .filter((e) => e && e.includes("@"));

    let audienceCount = 0;
    if (selectedAudienceId) {
      const aud = audiences.find((a) => a.id === selectedAudienceId);
      audienceCount = aud?.member_count || 0;
    }

    const raw = (audienceSource === "manual" ? manualEmails.length : audienceSource === "audience" ? audienceCount : manualEmails.length + audienceCount);
    const suppressed = suppressions.length;
    const excluded = exclusionsList.length;
    const finalCount = Math.max(0, raw - suppressed - excluded);

    return { raw, suppressed, excluded, final: finalCount };
  };

  const audienceCalc = calculateAudienceBreakdown();

  // Template Selection Change
  const handleTemplateSelect = (key) => {
    setSelectedTemplateKey(key);
    if (key === "custom") {
      return;
    }
    const found = templates.find((t) => t.key === key);
    if (found) {
      setEmailSubject(found.subject || "");
      setEmailHtml(found.body_html || "");
    }
  };

  // Insert Variable at cursor
  const handleInsertPlaceholder = (placeholder) => {
    if (!textareaRef.current) {
      setEmailHtml((prev) => prev + " " + placeholder);
      return;
    }
    const start = textareaRef.current.selectionStart;
    const end = textareaRef.current.selectionEnd;
    const current = emailHtml;
    const updated = current.substring(0, start) + placeholder + current.substring(end);
    setEmailHtml(updated);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + placeholder.length;
      }
    }, 50);
  };

  // Send Test Email from Composer
  const handleSendTestEmail = async () => {
    if (!testRecipient) {
      toast({ variant: "destructive", title: "Missing Test Recipient", description: "Please enter a test recipient email." });
      return;
    }
    if (!emailSubject.trim()) {
      toast({ variant: "destructive", title: "Missing Subject", description: "Email subject line is required." });
      return;
    }

    setSendingTestFromComposer(true);
    try {
      const resp = await api.post("/admin/communications/send-test", {
        recipient_email: testRecipient,
        recipient_name: "Test Administrator",
        template_key: selectedTemplateKey,
        variables: {
          name: "Test Administrator",
          company: "Navigatte Enterprise",
          email: testRecipient,
          service_interest: "Cloud Advisory & Modernization",
          start_time: "Aug 25, 2026, 2:00 PM UTC",
          meeting_url: "https://navigatte.com/meet/demo",
          unsubscribe_url: `https://navigatte.com/unsubscribe?email=${testRecipient}`,
        },
      });

      if (resp.data.success) {
        toast({
          title: "Test Email Dispatched",
          description: `Dispatched '${emailSubject}' to ${testRecipient} (Status: ${resp.data.status}).`,
        });
        reloadAll();
      } else {
        toast({
          variant: "destructive",
          title: resp.data.status === "provider_disabled" ? "Provider Not Configured" : "Dispatch Failed",
          description: resp.data.error_message || `Delivery status: ${resp.data.status}`,
        });
      }
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Dispatch Error",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setSendingTestFromComposer(false);
    }
  };

  // Save Campaign Draft
  const handleSaveCampaignDraft = async () => {
    if (!campTitle.trim()) {
      toast({ variant: "destructive", title: "Missing Title", description: "Please enter a campaign title." });
      return;
    }

    setSavingCampaignDraft(true);
    try {
      const manualList = manualRecipientsText
        .split(/[\n,;]/)
        .map((e) => e.trim().toLowerCase())
        .filter((e) => e && e.includes("@"));

      const payload = {
        name: campTitle,
        environment: sendMode,
        subject: emailSubject || "Navigatte Communication",
        template_key: selectedTemplateKey,
        audience_id: selectedAudienceId || null,
        audience_source: audienceSource,
        manual_recipients: manualList,
        exclusions: exclusionsList,
        custom_html: emailHtml,
        test_recipients: [testRecipient],
      };

      if (currentCampaignId) {
        await api.put(`/admin/communications/campaigns/${currentCampaignId}`, payload);
        toast({ title: "Campaign Updated", description: `Draft '${campTitle}' updated successfully.` });
      } else {
        const resp = await api.post("/admin/communications/campaigns", payload);
        setCurrentCampaignId(resp.data.id);
        toast({ title: "Campaign Created", description: `Draft '${campTitle}' saved successfully.` });
      }
      reloadAll();
    } catch (err) {
      toast({ variant: "destructive", title: "Save Failed", description: err.response?.data?.detail || err.message });
    } finally {
      setSavingCampaignDraft(false);
    }
  };

  // Pre-Flight Validation & Launch
  const handleOpenLaunchChecklist = async () => {
    if (!campTitle.trim()) {
      toast({ variant: "destructive", title: "Campaign Title Required", description: "Save or name your campaign before launching." });
      return;
    }

    await handleSaveCampaignDraft();

    try {
      if (!currentCampaignId) return;
      const resp = await api.get(`/admin/communications/campaigns/${currentCampaignId}/validate`);
      setLaunchChecklistModal({ campaignId: currentCampaignId, validation: resp.data });
    } catch (err) {
      toast({ variant: "destructive", title: "Validation Error", description: err.response?.data?.detail || err.message });
    }
  };

  const handleExecuteLaunch = async () => {
    if (!launchChecklistModal?.campaignId) return;
    setLaunchingCampaign(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${launchChecklistModal.campaignId}/launch`);
      toast({
        title: "Campaign Launched",
        description: resp.data.message,
      });
      setLaunchChecklistModal(null);
      setActiveTab("campaigns");
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

  // Retry Single Outbox Item
  const handleRetryOutbox = async (outboxId) => {
    setRetryingItem(true);
    try {
      const resp = await api.post(`/admin/communications/outbox/${outboxId}/retry`);
      if (resp.data.success) {
        toast({ title: "Retry Sent", description: `Message ${outboxId} dispatched successfully.` });
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

  // CSV Import Submission
  const handleExecuteCsvImport = async (audienceId) => {
    if (!csvImportText.trim()) {
      toast({ variant: "destructive", title: "Empty Data", description: "Paste CSV or email records to import." });
      return;
    }
    setImportingCsv(true);
    try {
      const lines = csvImportText.split("\n").map((l) => l.trim()).filter(Boolean);
      const contacts = lines.map((line) => {
        const parts = line.split(",").map((p) => p.trim());
        return {
          email: parts[0],
          name: parts[1] || "",
          company: parts[2] || "",
        };
      });

      const resp = await api.post(`/admin/communications/audiences/${audienceId}/import`, { contacts });
      setCsvImportResult(resp.data);
      toast({
        title: "Import Completed",
        description: `Imported ${resp.data.imported_count} contacts (${resp.data.suppressed_count} suppressed, ${resp.data.invalid_count} invalid).`,
      });
      reloadAll();
    } catch (err) {
      toast({ variant: "destructive", title: "Import Failed", description: err.response?.data?.detail || err.message });
    } finally {
      setImportingCsv(false);
    }
  };

  // Render Live Preview with placeholder replacement
  const getRenderedPreviewHtml = () => {
    let html = emailHtml;
    const sample = {
      "{{name}}": "Sarah Connor",
      "{{company}}": "Cyberdyne Systems",
      "{{email}}": testRecipient,
      "{{service_interest}}": "Enterprise Architecture",
      "{{start_time}}": "Aug 25, 2026, 2:00 PM UTC",
      "{{meeting_url}}": "https://navigatte.com/meet/demo",
      "{{unsubscribe_url}}": `https://navigatte.com/unsubscribe?email=${testRecipient}`,
    };

    Object.entries(sample).forEach(([k, v]) => {
      html = html.split(k).join(v);
    });

    return html;
  };

  return (
    <div className="space-y-6" data-testid="communications-centre">
      {/* Header & Environment Indicator */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-display font-light text-cloud">
              Communication Center
            </h1>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-[11px] font-mono uppercase bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {sendMode === "test" ? "TEST MODE" : "PRODUCTION"}
            </div>
          </div>
          <p className="text-xs text-fog mt-1">
            Compose, test, review, and dispatch verified email campaigns to your audience.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
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

      {/* Safety Layer Banner: Configured Test Recipient */}
      <div className="bg-emerald-950/20 border border-emerald-500/25 rounded-xl p-4 space-y-2">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider font-mono">
            <ShieldCheck className="w-4 h-4" />
            TEST MODE ACTIVE (Safety Layer 1 & 2 Enforced)
          </div>
          <span className="text-[11px] text-emerald-400/80 font-mono">
            Audience broadcasts safely blocked in test mode
          </span>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 pt-1">
          <span className="text-xs text-fog font-medium">CONFIGURED TEST RECIPIENT:</span>
          {editingTestRecipient ? (
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Input
                value={testRecipientInput}
                onChange={(e) => setTestRecipientInput(e.target.value)}
                placeholder="test@navigatte.com"
                className="h-7 text-xs bg-black/40 border-emerald-500/40 text-emerald-300 w-64"
              />
              <Button
                size="sm"
                onClick={() => {
                  setTestRecipient(testRecipientInput);
                  setEditingTestRecipient(false);
                  toast({ title: "Test Recipient Set", description: `Test sends will deliver to ${testRecipientInput}` });
                }}
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] h-7 px-2.5"
              >
                Save
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-mono text-xs">
                {testRecipient}
              </span>
              <button
                onClick={() => setEditingTestRecipient(true)}
                className="text-[11px] text-emerald-400 hover:underline font-medium"
              >
                Change Recipient
              </button>
            </div>
          )}
        </div>
        <p className="text-[11px] text-emerald-400/70 font-mono">
          In Test Mode, emails are dispatched ONLY to the single server-controlled test recipient above.
        </p>
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
      {/* TAB 1: CAMPAIGN STUDIO (Upgraded 2-Pane Composer & Safety Pipeline) */}
      {/* ========================================================================= */}
      {activeTab === "composer" && (
        <div className="space-y-6">
          {/* Section 1: Campaign Send Mode & Title */}
          <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
            <span className="text-xs font-mono uppercase tracking-wider text-fog">1. Campaign Configuration</span>

            {/* Mode Selector */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                onClick={() => setSendMode("test")}
                className={`p-3.5 rounded-xl border text-left flex items-start gap-3 transition-all ${
                  sendMode === "test"
                    ? "bg-emerald-950/30 border-emerald-500/50 text-cloud"
                    : "bg-white/[0.02] border-white/10 text-fog hover:bg-white/[0.04]"
                }`}
              >
                <div className={`p-2 rounded-lg ${sendMode === "test" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-fog"}`}>
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-cloud flex items-center gap-1.5">
                    TEST MODE (Sandbox)
                    {sendMode === "test" && <span className="text-[10px] text-emerald-400 font-mono">ACTIVE</span>}
                  </div>
                  <p className="text-[11px] text-fog mt-0.5">Strictly delivers only to configured test recipient</p>
                </div>
              </button>

              <button
                onClick={() => setSendMode("production")}
                className={`p-3.5 rounded-xl border text-left flex items-start gap-3 transition-all ${
                  sendMode === "production"
                    ? "bg-iris/20 border-iris text-cloud"
                    : "bg-white/[0.02] border-white/10 text-fog hover:bg-white/[0.04]"
                }`}
              >
                <div className={`p-2 rounded-lg ${sendMode === "production" ? "bg-iris/30 text-iris" : "bg-white/5 text-fog"}`}>
                  <Send className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-cloud flex items-center gap-1.5">
                    PRODUCTION MODE
                    {sendMode === "production" && <span className="text-[10px] text-iris font-mono">ACTIVE</span>}
                  </div>
                  <p className="text-[11px] text-fog mt-0.5">Live broadcast — requires 2-step verification & freeze</p>
                </div>
              </button>
            </div>

            {/* Campaign Title */}
            <div>
              <label className="block text-xs text-fog mb-1.5 font-medium">CAMPAIGN TITLE</label>
              <Input
                placeholder="e.g. Q3 Advisory & Regulatory Strategy Update"
                value={campTitle}
                onChange={(e) => setCampTitle(e.target.value)}
                className="bg-white/5 border-white/10 text-cloud text-xs h-9"
              />
            </div>

            {/* Audience Source Selector */}
            <div className="space-y-2 pt-2 border-t border-white/5">
              <label className="block text-xs text-fog font-medium">RECIPIENT AUDIENCE SOURCE</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {[
                  { id: "newsletter", title: "Newsletter Subscribers", badge: "OPTED-IN", desc: "Explicit website opt-ins via PSA insights forms" },
                  { id: "manual", title: "Manual Recipients", badge: "TARGETED", desc: "Admin-entered verified email list / chips / paste" },
                  { id: "both", title: "Both Sources", badge: "FULL REACH", desc: "Newsletter subscribers + manual recipient list, deduplicated" },
                ].map((src) => (
                  <button
                    key={src.id}
                    onClick={() => setAudienceSource(src.id)}
                    className={`p-3 rounded-xl border text-left transition-all ${
                      audienceSource === src.id
                        ? "bg-iris/15 border-iris/40 text-cloud"
                        : "bg-white/[0.02] border-white/10 text-fog hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-cloud">{src.title}</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-fog">{src.badge}</span>
                    </div>
                    <p className="text-[10px] text-fog mt-1">{src.desc}</p>
                  </button>
                ))}
              </div>

              {/* Manual Recipients Input if manual/both */}
              {(audienceSource === "manual" || audienceSource === "both") && (
                <div className="pt-2">
                  <label className="block text-[11px] text-fog mb-1">MANUAL EMAIL RECIPIENTS (Comma or newline separated)</label>
                  <textarea
                    rows={2}
                    value={manualRecipientsText}
                    onChange={(e) => setManualRecipientsText(e.target.value)}
                    placeholder="client1@enterprise.com, partner@advisory.io"
                    className="w-full bg-white/5 border border-white/10 rounded-lg p-2.5 text-xs text-cloud font-mono outline-none focus:border-iris resize-y"
                  />
                </div>
              )}

              {/* Authoritative Audience Calculation Bar */}
              <div className="p-3 bg-black/40 border border-white/10 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 text-cloud font-medium">
                  <Users className="w-4 h-4 text-iris" />
                  <span>AUTHORITATIVE AUDIENCE CALCULATION:</span>
                  <span className="text-emerald-400 font-mono font-semibold">{audienceCalc.final} Net Verified Recipients</span>
                </div>

                <div className="flex items-center gap-3 font-mono text-[11px] text-fog">
                  <span>Raw: <strong className="text-cloud">{audienceCalc.raw}</strong></span>
                  <span>Suppressed: <strong className="text-amber-400">{audienceCalc.suppressed}</strong></span>
                  <span>Excluded: <strong className="text-rose-400">{audienceCalc.excluded}</strong></span>
                  <button
                    onClick={() => setExclusionsModalOpen(true)}
                    className="text-iris hover:underline ml-2"
                  >
                    Manage Exclusions ({exclusionsList.length})
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Section 2: Compose Email Content (2-Pane Editor + Live Preview) */}
          <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs font-mono uppercase tracking-wider text-fog">2. Compose Email Content</span>
                <p className="text-[11px] text-fog">Select a template or write custom HTML. What you see is exactly what will be sent.</p>
              </div>

              {/* Template Picker */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-fog font-medium">TEMPLATE:</span>
                <select
                  value={selectedTemplateKey}
                  onChange={(e) => handleTemplateSelect(e.target.value)}
                  className="h-8 text-xs bg-white/5 border border-white/10 text-cloud rounded-lg px-2.5 outline-none font-mono"
                >
                  <option value="custom" className="bg-[#101018]">-- Custom Template --</option>
                  {templates.map((tpl) => (
                    <option key={tpl.key} value={tpl.key} className="bg-[#101018]">
                      {tpl.name} (v{tpl.version || 1})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Email Subject */}
            <div>
              <label className="block text-xs text-fog mb-1 font-medium">EMAIL SUBJECT LINE</label>
              <Input
                placeholder="e.g. Important Regulatory & Tax Advisory Update"
                value={emailSubject}
                onChange={(e) => setEmailSubject(e.target.value)}
                className="bg-white/5 border-white/10 text-cloud text-xs h-9"
              />
            </div>

            {/* Insert Placeholders Toolbar */}
            <div className="flex items-center gap-1.5 flex-wrap pt-1">
              <span className="text-[11px] text-iris flex items-center gap-1 font-mono uppercase">
                <Sparkles className="w-3 h-3" /> Placeholders:
              </span>
              {PLACEHOLDERS.map((ph) => (
                <button
                  key={ph.label}
                  type="button"
                  onClick={() => handleInsertPlaceholder(ph.label)}
                  title={ph.desc}
                  className="px-2 py-0.5 rounded bg-white/5 hover:bg-iris/20 text-[10px] font-mono text-cloud border border-white/10 transition-colors"
                >
                  {ph.label}
                </button>
              ))}
            </div>

            {/* 2-Pane Editor & Live Preview */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
              {/* Left Pane: HTML Content Body */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-fog">
                  <span className="font-mono flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-iris" /> HTML CONTENT BODY
                  </span>
                  <span className="text-[10px] text-fog/60 font-mono">Exact authored HTML sent as-is</span>
                </div>
                <textarea
                  ref={textareaRef}
                  rows={16}
                  value={emailHtml}
                  onChange={(e) => setEmailHtml(e.target.value)}
                  className="w-full bg-[#0a0a0f] border border-white/10 rounded-xl p-3 text-xs text-cloud font-mono outline-none focus:border-iris resize-y leading-relaxed"
                />
              </div>

              {/* Right Pane: Real-Time Preview */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-fog">
                  <span className="font-mono flex items-center gap-1.5">
                    <Eye className="w-3.5 h-3.5 text-emerald-400" /> REAL-TIME EMAIL PREVIEW
                  </span>
                  <div className="flex items-center gap-1 bg-white/5 p-0.5 rounded border border-white/10">
                    <button
                      onClick={() => setPreviewViewport("desktop")}
                      className={`p-1 rounded text-[10px] flex items-center gap-1 ${
                        previewViewport === "desktop" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                      }`}
                    >
                      <Monitor className="w-3 h-3" /> Desktop
                    </button>
                    <button
                      onClick={() => setPreviewViewport("mobile")}
                      className={`p-1 rounded text-[10px] flex items-center gap-1 ${
                        previewViewport === "mobile" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                      }`}
                    >
                      <Smartphone className="w-3 h-3" /> Mobile
                    </button>
                  </div>
                </div>

                <div
                  className={`border border-white/10 rounded-xl overflow-hidden bg-white shadow-inner mx-auto transition-all ${
                    previewViewport === "mobile" ? "max-w-[340px]" : "w-full"
                  }`}
                  style={{ height: "350px" }}
                >
                  <iframe
                    title="Email Live Preview"
                    srcDoc={getRenderedPreviewHtml()}
                    className="w-full h-full border-0 bg-white"
                  />
                </div>
              </div>
            </div>

            {/* Bottom Actions Bar */}
            <div className="pt-4 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Button
                  onClick={handleSaveCampaignDraft}
                  disabled={savingCampaignDraft}
                  variant="outline"
                  size="sm"
                  className="border-white/10 text-cloud hover:bg-white/5 text-xs h-9"
                >
                  {savingCampaignDraft ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Edit3 className="w-3.5 h-3.5 mr-1.5" />}
                  Save Draft
                </Button>
              </div>

              <div className="flex items-center gap-2">
                {sendMode === "test" ? (
                  <Button
                    onClick={handleSendTestEmail}
                    disabled={sendingTestFromComposer}
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-9 px-4 font-medium shadow-lg"
                  >
                    {sendingTestFromComposer ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                    ) : (
                      <Send className="w-3.5 h-3.5 mr-1.5" />
                    )}
                    Send Test Email → {testRecipient}
                  </Button>
                ) : (
                  <Button
                    onClick={handleOpenLaunchChecklist}
                    size="sm"
                    className="bg-iris hover:bg-iris/90 text-white text-xs h-9 px-4 font-medium shadow-lg"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                    Review Checklist & Launch Campaign
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
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
                setActiveTab("composer");
                setCurrentCampaignId(null);
                setCampTitle("");
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
                  <p><strong className="text-cloud">Template:</strong> {camp.template_key}</p>
                </div>

                <div className="pt-2 border-t border-white/5 flex items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      setCurrentCampaignId(camp.id);
                      setCampTitle(camp.name);
                      setEmailSubject(camp.subject);
                      setSelectedTemplateKey(camp.template_key);
                      if (camp.custom_html) setEmailHtml(camp.custom_html);
                      setSendMode(camp.environment || "test");
                      setActiveTab("composer");
                    }}
                    className="text-iris hover:underline text-xs"
                  >
                    Load into Composer
                  </button>
                  <Button
                    onClick={() => {
                      setCurrentCampaignId(camp.id);
                      handleOpenLaunchChecklist();
                    }}
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

      {/* ========================================================================= */}
      {/* TAB 3: TEMPLATES LIBRARY */}
      {/* ========================================================================= */}
      {activeTab === "templates" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Email Templates Library ({templates.length})</h3>
            <Button
              size="sm"
              onClick={() => {
                setActiveTab("composer");
                setSelectedTemplateKey("custom");
              }}
              className="bg-iris text-white text-xs h-8"
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> Create Template
            </Button>
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
                      setSelectedTemplateKey(tpl.key);
                      setEmailSubject(tpl.subject);
                      setEmailHtml(tpl.body_html);
                      setActiveTab("composer");
                    }}
                    className="text-iris hover:underline text-xs"
                  >
                    Open in Composer
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
                    <History className="w-3.5 h-3.5" /> Versions
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
              <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Audience Groups</h3>
            </div>
            <div className="bg-obsidian border border-white/10 rounded-xl divide-y divide-white/5">
              {audiences.length === 0 ? (
                <div className="p-6 text-center text-fog text-xs">No audience groups defined.</div>
              ) : (
                audiences.map((aud) => (
                  <div key={aud.id} className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-cloud">{aud.name}</h4>
                      <span className="text-xs font-mono text-iris">{aud.member_count} contacts</span>
                    </div>
                    <p className="text-xs text-fog">{aud.description || "No description."}</p>
                    <div className="pt-1 flex items-center gap-2">
                      <Button
                        onClick={() => {
                          setCsvImportModal(aud);
                          setCsvImportText("");
                          setCsvImportResult(null);
                        }}
                        size="sm"
                        variant="outline"
                        className="border-white/10 text-cloud hover:bg-white/5 text-[11px] h-7"
                      >
                        <Upload className="w-3 h-3 mr-1" /> Import CSV / Contacts
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

      {/* Exclusions Modal */}
      {exclusionsModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud">Campaign Exclusions</h3>
              <button onClick={() => setExclusionsModalOpen(false)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <p className="text-xs text-fog">
              Add specific emails or entire domains (e.g. <code>@navigatte.com</code>) to exclude from this campaign.
            </p>

            <div className="flex items-center gap-2">
              <Input
                placeholder="e.g. @domain.com or user@email.com"
                value={newExclusionInput}
                onChange={(e) => setNewExclusionInput(e.target.value)}
                className="text-xs bg-white/5 border-white/10 text-cloud h-8"
              />
              <Button
                size="sm"
                onClick={() => {
                  if (newExclusionInput.trim()) {
                    setExclusionsList((prev) => [...prev, newExclusionInput.trim()]);
                    setNewExclusionInput("");
                  }
                }}
                className="bg-iris text-white text-xs h-8 px-3"
              >
                Add
              </Button>
            </div>

            <div className="space-y-1.5 max-h-48 overflow-y-auto pt-2">
              {exclusionsList.map((excl, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 rounded bg-white/5 text-xs">
                  <span className="font-mono text-cloud">{excl}</span>
                  <button
                    onClick={() => setExclusionsList((prev) => prev.filter((_, i) => i !== idx))}
                    className="text-rose-400 hover:text-rose-300 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-end">
              <Button onClick={() => setExclusionsModalOpen(false)} className="bg-iris text-white text-xs h-8">
                Done
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Pre-Flight Launch Checklist Modal */}
      {launchChecklistModal && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Pre-Flight Launch Checklist
              </h3>
              <button onClick={() => setLaunchChecklistModal(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2.5 bg-white/5 rounded">
                <span>Environment Match ({launchChecklistModal.validation.checklist.environment})</span>
                <span className={launchChecklistModal.validation.checklist.environment_confirmed ? "text-emerald-400 font-mono" : "text-rose-400 font-mono"}>
                  {launchChecklistModal.validation.checklist.environment_confirmed ? "✓ Confirmed" : "✗ Mismatch"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 bg-white/5 rounded">
                <span>Provider Connection</span>
                <span className={launchChecklistModal.validation.checklist.provider_healthy ? "text-emerald-400 font-mono" : "text-rose-400 font-mono"}>
                  {launchChecklistModal.validation.checklist.provider_healthy ? "✓ Active" : "✗ Unconfigured"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 bg-white/5 rounded">
                <span>Net Target Deliverable</span>
                <span className="font-mono text-iris font-semibold">
                  {launchChecklistModal.validation.checklist.target_recipients_count} recipients
                </span>
              </div>
            </div>

            {launchChecklistModal.validation.errors?.length > 0 && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/25 rounded text-xs text-rose-300 space-y-1 font-mono">
                <p className="font-semibold uppercase text-[10px]">Blocking Checklist Errors:</p>
                {launchChecklistModal.validation.errors.map((err, i) => (
                  <p key={i}>• {err}</p>
                ))}
              </div>
            )}

            <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setLaunchChecklistModal(null)} className="border-white/10 text-ash text-xs h-8">
                Cancel
              </Button>
              <Button
                disabled={!launchChecklistModal.validation.is_valid || launchingCampaign}
                onClick={handleExecuteLaunch}
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8 px-4"
              >
                {launchingCampaign ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Play className="w-3.5 h-3.5 mr-1" />}
                Confirm & Launch Broadcast
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* CSV Import Modal */}
      {csvImportModal && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud">Import Contacts into {csvImportModal.name}</h3>
              <button onClick={() => setCsvImportModal(null)} className="text-fog hover:text-cloud text-xs">✕</button>
            </div>

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

            {csvImportResult && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/25 rounded text-xs text-emerald-300 space-y-1 font-mono">
                <p>Total Rows: {csvImportResult.total_rows}</p>
                <p>Imported: {csvImportResult.imported_count}</p>
                <p>Suppressed: {csvImportResult.suppressed_count}</p>
                <p>Duplicates / Invalid: {csvImportResult.duplicate_count + csvImportResult.invalid_count}</p>
              </div>
            )}

            <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setCsvImportModal(null)} className="border-white/10 text-ash text-xs h-8">
                Close
              </Button>
              <Button
                disabled={importingCsv}
                onClick={() => handleExecuteCsvImport(csvImportModal.id)}
                size="sm"
                className="bg-iris text-white text-xs h-8"
              >
                {importingCsv ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Upload className="w-3.5 h-3.5 mr-1" />}
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
                    className="border-white/10 text-cloud text-xs h-7"
                  >
                    Restore
                  </Button>
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
    </div>
  );
};

export default CommunicationsCentre;
