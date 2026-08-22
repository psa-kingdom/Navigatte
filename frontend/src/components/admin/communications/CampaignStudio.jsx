/**
 * CampaignStudio — One-Screen Email Campaign Composer
 *
 * This component is the core of the Communications Centre. It provides a
 * complete campaign authoring experience without requiring navigation between
 * multiple screens:
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────┐
 *   │  Campaign Identity Bar (name, env, autosave)     │
 *   ├─────────────────────┬───────────────────────────┤
 *   │  LEFT: Editor       │  RIGHT: Live Preview       │
 *   │  - Source toggle    │  - Sandboxed iframe        │
 *   │  - Subject line     │  - Desktop/Mobile toggle   │
 *   │  - HTML textarea    │  - Unresolved var warnings │
 *   │  - Variable toolbar │                            │
 *   ├─────────────────────┴───────────────────────────┤
 *   │  Recipients (chips + audience + exclusions)      │
 *   │  Test Recipients + Send Test button              │
 *   │  Launch Bar (Save | Preview | Review & Launch)   │
 *   └─────────────────────────────────────────────────┘
 *
 * Architectural invariant: preview == test == outbox snapshot == sent email.
 * The preview iframe always shows the rendered output of render_message() via
 * a frontend substitution using the same variable set.
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Send,
  CheckCircle2,
  AlertTriangle,
  Eye,
  Search,
  Clock,
  FileText,
  Loader2,
  ShieldCheck,
  Users,
  Play,
  FileCode,
  Smartphone,
  Monitor,
  Check,
  Sparkles,
  Mail,
  RefreshCw,
  Save,
  Zap,
  X,
  Plus,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";
import { RecipientChips } from "./RecipientChips";
import { ProductionSafetyModal } from "./ProductionSafetyModal";

// Available {{ variable }} placeholders for the toolbar
const PLACEHOLDERS = [
  { label: "{{name}}", desc: "Recipient full name" },
  { label: "{{company}}", desc: "Company / organization" },
  { label: "{{email}}", desc: "Recipient email" },
  { label: "{{service_interest}}", desc: "Consulting interest" },
  { label: "{{start_time}}", desc: "Scheduled meeting date/time" },
  { label: "{{meeting_url}}", desc: "Cal.com / video link" },
  { label: "{{unsubscribe_url}}", desc: "Signed opt-out URL (auto-generated)" },
];

const SAMPLE_VARS = {
  "{{name}}": "Sarah Connor",
  "{{company}}": "Cyberdyne Systems",
  "{{email}}": "sarah@cyberdyne.io",
  "{{service_interest}}": "Cloud & AI Architecture",
  "{{start_time}}": "Aug 25, 2026, 2:00 PM UTC",
  "{{meeting_url}}": "https://navigatte.com/meet/demo",
  "{{unsubscribe_url}}": "https://navigatte.com/api/unsubscribe?email=sarah@cyberdyne.io&token=preview",
};

const AUTOSAVE_DEBOUNCE_MS = 30000; // 30s server autosave
const LOCAL_SAVE_DEBOUNCE_MS = 2000;  // 2s localStorage save

const DEFAULT_HTML = `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1e293b; line-height: 1.6;">
  <h2 style="color: #0f172a;">Navigatte Advisory &amp; Strategy Briefing</h2>
  <p>Hello {{name}},</p>
  <p>We are pleased to share our latest architecture and engineering advisory update.</p>
  <p>If you have questions regarding your project roadmap at {{company}}, let us know.</p>
  <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
  <p style="font-size: 12px; color: #64748b;">Navigatte Strategy &amp; Engineering &bull;
    <a href="{{unsubscribe_url}}" style="color: #6366f1;">Unsubscribe</a>
  </p>
</div>`;

/**
 * Renders live preview HTML by substituting {{ var }} with sample values.
 * This matches what the backend render_message() would produce with sample vars.
 */
function buildPreviewHtml(html) {
  let rendered = html;
  Object.entries(SAMPLE_VARS).forEach(([k, v]) => {
    rendered = rendered.split(k).join(v);
  });
  return rendered;
}

/**
 * Detects any {{ var }} placeholders remaining after sample substitution.
 */
function detectUnresolvedVars(html) {
  const matches = html.match(/\{\{\s*\w+\s*\}\}/g) || [];
  return [...new Set(matches)];
}

export const CampaignStudio = ({
  templates = [],
  audiences = [],
  suppressions = [],
  diagnostics = null,
  onCampaignSaved = () => {},
  onCampaignLaunched = () => {},
  initialCampaign = null,
}) => {
  const { toast } = useToast();
  const textareaRef = useRef(null);
  const autosaveTimerRef = useRef(null);
  const localSaveTimerRef = useRef(null);

  // ── Identity & Config ────────────────────────────────────────────────────
  const [campTitle, setCampTitle] = useState(initialCampaign?.name || "");
  const [campId, setCampId] = useState(initialCampaign?.id || null);
  const [autosaveStatus, setAutosaveStatus] = useState("idle"); // idle | saving | saved | error

  // ── Content Source ───────────────────────────────────────────────────────
  const [contentSource, setContentSource] = useState("custom"); // 'custom' | template key
  const [selectedTemplateKey, setSelectedTemplateKey] = useState("custom");
  const [emailSubject, setEmailSubject] = useState(initialCampaign?.subject || "");
  const [emailHtml, setEmailHtml] = useState(initialCampaign?.custom_html || DEFAULT_HTML);

  // ── Preview ──────────────────────────────────────────────────────────────
  const [previewViewport, setPreviewViewport] = useState("desktop");
  const [serverPreview, setServerPreview] = useState(null); // { subject, html_body }
  const [loadingPreview, setLoadingPreview] = useState(false);

  // ── Recipients ───────────────────────────────────────────────────────────
  const [audienceSource, setAudienceSource] = useState(
    initialCampaign?.audience_source || "audience"
  );
  const [selectedAudienceId, setSelectedAudienceId] = useState(
    initialCampaign?.audience_id || ""
  );
  const [manualRecipients, setManualRecipients] = useState(
    initialCampaign?.manual_recipients || []
  );
  const [exclusions, setExclusions] = useState(
    initialCampaign?.exclusions || ["@navigatte.com"]
  );
  const [exclusionInput, setExclusionInput] = useState("");
  const [recipientBreakdown, setRecipientBreakdown] = useState(null);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);

  // ── Test Section ─────────────────────────────────────────────────────────
  const [testRecipients, setTestRecipients] = useState(
    initialCampaign?.test_recipients || []
  );
  const [sendingTest, setSendingTest] = useState(false);

  // ── Launch Flow ──────────────────────────────────────────────────────────
  const [savingDraft, setSavingDraft] = useState(false);
  const [validating, setValidating] = useState(false);
  const [safetyModalOpen, setSafetyModalOpen] = useState(false);
  const [launchChecklist, setLaunchChecklist] = useState(null);
  const [launchPreviewHtml, setLaunchPreviewHtml] = useState("");
  const [launching, setLaunching] = useState(false);

  // ── Derived ──────────────────────────────────────────────────────────────
  const environment = diagnostics?.environment?.current || "test";
  const isProductionMode = environment === "production";
  const workerRunning = diagnostics?.worker?.status === "running";
  const fromEmail = diagnostics?.provider?.from_email || "Navigatte <updates@updates.navigatte.com>";
  const previewHtml = serverPreview?.html_body || buildPreviewHtml(emailHtml);
  const previewSubject = serverPreview?.subject || buildPreviewHtml(emailSubject);
  const unresolvedVars = detectUnresolvedVars(previewHtml);

  // ── Local Storage Draft ──────────────────────────────────────────────────
  useEffect(() => {
    if (!campId) return;
    const saved = localStorage.getItem(`campaign_draft_${campId}`);
    if (saved) {
      try {
        const d = JSON.parse(saved);
        if (d.emailHtml) setEmailHtml(d.emailHtml);
        if (d.emailSubject) setEmailSubject(d.emailSubject);
        if (d.campTitle) setCampTitle(d.campTitle);
      } catch (e) { /* ignore */ }
    }
  }, [campId]);

  const saveToLocalStorage = useCallback(() => {
    if (!campId) return;
    try {
      localStorage.setItem(`campaign_draft_${campId}`, JSON.stringify({
        emailHtml, emailSubject, campTitle, savedAt: Date.now(),
      }));
    } catch (e) { /* ignore */ }
  }, [campId, emailHtml, emailSubject, campTitle]);

  // Debounced local save
  useEffect(() => {
    clearTimeout(localSaveTimerRef.current);
    localSaveTimerRef.current = setTimeout(saveToLocalStorage, LOCAL_SAVE_DEBOUNCE_MS);
    return () => clearTimeout(localSaveTimerRef.current);
  }, [emailHtml, emailSubject, campTitle, saveToLocalStorage]);

  // ── Template Selection ───────────────────────────────────────────────────
  const handleTemplateSelect = (key) => {
    setSelectedTemplateKey(key);
    setContentSource(key === "custom" ? "custom" : key);
    if (key !== "custom") {
      const tpl = templates.find((t) => t.key === key);
      if (tpl) {
        setEmailSubject(tpl.subject || "");
        setEmailHtml(tpl.body_html || "");
      }
    }
    setServerPreview(null); // Clear cached preview on content change
  };

  // ── Insert Variable at Cursor ────────────────────────────────────────────
  const handleInsertPlaceholder = (placeholder) => {
    if (!textareaRef.current) {
      setEmailHtml((prev) => prev + " " + placeholder);
      return;
    }
    const start = textareaRef.current.selectionStart;
    const end = textareaRef.current.selectionEnd;
    const updated = emailHtml.substring(0, start) + placeholder + emailHtml.substring(end);
    setEmailHtml(updated);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const pos = start + placeholder.length;
        textareaRef.current.selectionStart = textareaRef.current.selectionEnd = pos;
      }
    }, 50);
    setServerPreview(null);
  };

  // ── Collect Current Campaign Payload ─────────────────────────────────────
  const getCampaignPayload = useCallback(() => ({
    name: campTitle.trim() || "Untitled Campaign",
    environment,
    subject: emailSubject || "Navigatte Communication",
    template_key: selectedTemplateKey,
    audience_id: selectedAudienceId || null,
    audience_source: audienceSource,
    manual_recipients: manualRecipients,
    exclusions,
    custom_html: emailHtml,
    test_recipients: testRecipients,
  }), [campTitle, environment, emailSubject, selectedTemplateKey, selectedAudienceId,
       audienceSource, manualRecipients, exclusions, emailHtml, testRecipients]);

  // ── Save Draft ───────────────────────────────────────────────────────────
  const handleSaveDraft = useCallback(async (silent = false) => {
    if (!campTitle.trim() && !silent) {
      toast({ variant: "destructive", title: "Campaign name required", description: "Add a name before saving." });
      return null;
    }
    setSavingDraft(!silent);
    setAutosaveStatus("saving");
    try {
      const payload = getCampaignPayload();
      let id = campId;
      if (id) {
        await api.put(`/admin/communications/campaigns/${id}`, payload);
      } else {
        const resp = await api.post("/admin/communications/campaigns", {
          ...payload,
          name: payload.name || "Untitled Campaign",
        });
        id = resp.data.id;
        setCampId(id);
      }
      setAutosaveStatus("saved");
      if (!silent) {
        toast({ title: "Draft saved", description: `Campaign '${payload.name}' saved.` });
        onCampaignSaved(id);
      }
      setTimeout(() => setAutosaveStatus("idle"), 3000);
      return id;
    } catch (err) {
      setAutosaveStatus("error");
      if (!silent) {
        toast({ variant: "destructive", title: "Save failed", description: err.response?.data?.detail || err.message });
      }
      return null;
    } finally {
      setSavingDraft(false);
    }
  }, [campId, campTitle, getCampaignPayload, onCampaignSaved, toast]);

  // Debounced server autosave
  useEffect(() => {
    if (!campId) return;
    clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => handleSaveDraft(true), AUTOSAVE_DEBOUNCE_MS);
    return () => clearTimeout(autosaveTimerRef.current);
  }, [emailHtml, emailSubject, campTitle, manualRecipients, testRecipients, exclusions, campId, handleSaveDraft]);

  // ── Server-Side Preview ──────────────────────────────────────────────────
  const handleFetchServerPreview = async () => {
    // Save first to ensure the server has the latest content
    let id = campId;
    if (!id) {
      id = await handleSaveDraft(false);
      if (!id) return;
    } else {
      await handleSaveDraft(true);
    }

    setLoadingPreview(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${id}/render-preview`);
      setServerPreview({ subject: resp.data.subject, html_body: resp.data.html_body });
      if (resp.data.unresolved_variables?.length > 0) {
        toast({
          title: "Unresolved Variables Detected",
          description: `Found: ${resp.data.unresolved_variables.join(", ")}. These will appear literally in emails.`,
          variant: "destructive",
        });
      } else {
        toast({ title: "Preview Updated", description: "Showing exact content that will be dispatched." });
      }
    } catch (err) {
      toast({ variant: "destructive", title: "Preview failed", description: err.response?.data?.detail || err.message });
    } finally {
      setLoadingPreview(false);
    }
  };

  // ── Recipient Breakdown ──────────────────────────────────────────────────
  const handleCalculateBreakdown = async () => {
    if (!campId) {
      const id = await handleSaveDraft(false);
      if (!id) return;
    }
    setLoadingBreakdown(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${campId}/calculate-recipients`);
      setRecipientBreakdown(resp.data);
    } catch (err) {
      toast({ variant: "destructive", title: "Calculation failed", description: err.response?.data?.detail || err.message });
    } finally {
      setLoadingBreakdown(false);
    }
  };

  // ── Send Test ────────────────────────────────────────────────────────────
  const handleSendTest = async () => {
    if (testRecipients.length === 0) {
      toast({ variant: "destructive", title: "No test recipients", description: "Add at least one test recipient below." });
      return;
    }
    if (!emailSubject.trim()) {
      toast({ variant: "destructive", title: "Subject required", description: "Enter a subject line before sending." });
      return;
    }

    // Save first, then use send-test-campaign (server-enforced test isolation)
    let id = campId;
    if (!id) {
      id = await handleSaveDraft(false);
      if (!id) return;
    } else {
      await handleSaveDraft(true);
    }

    setSendingTest(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${id}/send-test-campaign`);
      if (resp.data.success) {
        toast({
          title: "Test Dispatched",
          description: `Sent to ${resp.data.sent_count}/${resp.data.test_recipients_count} test recipient(s).`,
        });
      } else {
        toast({
          variant: "destructive",
          title: resp.data.status === "provider_disabled" ? "Provider Not Configured" : "Test Failed",
          description: resp.data.error_message || `Failed: ${resp.data.failed_count} recipients.`,
        });
      }
    } catch (err) {
      toast({ variant: "destructive", title: "Test Error", description: err.response?.data?.detail || err.message });
    } finally {
      setSendingTest(false);
    }
  };

  // ── Review & Launch ──────────────────────────────────────────────────────
  const handleOpenLaunch = async () => {
    if (!campTitle.trim()) {
      toast({ variant: "destructive", title: "Campaign name required" });
      return;
    }
    if (!emailSubject.trim()) {
      toast({ variant: "destructive", title: "Subject required" });
      return;
    }

    setValidating(true);
    try {
      let id = campId;
      if (!id) {
        id = await handleSaveDraft(false);
        if (!id) return;
      } else {
        await handleSaveDraft(true);
      }

      // Get validation + preview in parallel
      const [valResp, previewResp] = await Promise.all([
        api.get(`/admin/communications/campaigns/${id}/validate`),
        api.post(`/admin/communications/campaigns/${id}/render-preview`).catch(() => null),
      ]);

      const validation = valResp.data;
      if (!validation.is_valid) {
        toast({
          variant: "destructive",
          title: "Campaign not ready",
          description: validation.errors?.join(". ") || "Fix checklist errors before launching.",
        });
        return;
      }

      setLaunchChecklist(validation.checklist);
      setLaunchPreviewHtml(previewResp?.data?.html_body || previewHtml);
      setSafetyModalOpen(true);
    } catch (err) {
      toast({ variant: "destructive", title: "Validation error", description: err.response?.data?.detail || err.message });
    } finally {
      setValidating(false);
    }
  };

  const handleConfirmLaunch = async () => {
    if (!campId) return;
    setLaunching(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${campId}/launch`);
      setSafetyModalOpen(false);
      toast({
        title: "Campaign Launched! 🚀",
        description: resp.data.message || `Campaign launched to ${resp.data.campaign?.total_recipients} recipients.`,
      });
      onCampaignLaunched(campId);
    } catch (err) {
      toast({ variant: "destructive", title: "Launch Failed", description: err.response?.data?.detail || err.message });
    } finally {
      setLaunching(false);
    }
  };

  // ── Exclusion Management ─────────────────────────────────────────────────
  const addExclusion = () => {
    const val = exclusionInput.trim().toLowerCase();
    if (!val || exclusions.includes(val)) return;
    setExclusions([...exclusions, val]);
    setExclusionInput("");
  };

  // ── Audience source options (no "newsletter" — no backing collection) ────
  const AUDIENCE_SOURCES = [
    { id: "audience", label: "Audience Only", desc: "Selected audience list members" },
    { id: "manual", label: "Manual Only", desc: "Manually entered email addresses" },
    { id: "both", label: "Audience + Manual", desc: "Combined, deduplicated" },
  ];

  return (
    <>
      {/* ── Identity Bar ──────────────────────────────────────────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex-1">
            <Input
              id="campaign-name-input"
              value={campTitle}
              onChange={(e) => setCampTitle(e.target.value)}
              placeholder="Campaign name (internal label, not shown to recipients)"
              className="bg-white/5 border-white/10 text-cloud text-sm h-9 font-medium"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0 text-xs">
            {/* Environment badge (from backend, not local toggle) */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border font-mono text-[10px] uppercase ${
              isProductionMode
                ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${isProductionMode ? "bg-rose-400" : "bg-emerald-400"}`} />
              {isProductionMode ? "PRODUCTION" : "TEST MODE"}
            </div>

            {/* Provider */}
            <div className="px-2.5 py-1 rounded-full border bg-white/5 border-white/10 text-fog font-mono text-[10px]">
              Provider: Resend
            </div>

            {/* Worker status */}
            <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full border font-mono text-[10px] ${
              workerRunning
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                : "bg-amber-500/10 border-amber-500/20 text-amber-400"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${workerRunning ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
              Worker {workerRunning ? "Running" : "Stopped"}
            </div>

            {/* Autosave indicator */}
            <div className="text-[10px] text-fog font-mono">
              {autosaveStatus === "saving" && <span className="text-iris animate-pulse">Saving…</span>}
              {autosaveStatus === "saved" && <span className="text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" /> Saved</span>}
              {autosaveStatus === "error" && <span className="text-rose-400">Save error</span>}
            </div>
          </div>
        </div>

        {/* Sender info */}
        <div className="mt-2 flex items-center gap-2 text-[11px] text-fog">
          <Mail className="w-3 h-3 text-fog/60" />
          <span>From: <span className="text-cloud font-mono">{fromEmail}</span></span>
        </div>
      </div>

      {/* ── 2-Pane: Editor + Preview ─────────────────────────────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <span className="text-xs font-mono uppercase tracking-wider text-fog">Email Content</span>
            <p className="text-[11px] text-fog/70 mt-0.5">Select a template or write custom HTML. Preview = exact email content.</p>
          </div>

          {/* Template/Custom toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-fog font-medium">Template:</span>
            <select
              value={selectedTemplateKey}
              onChange={(e) => handleTemplateSelect(e.target.value)}
              className="h-8 text-xs bg-white/5 border border-white/10 text-cloud rounded-lg px-2.5 outline-none font-mono focus:border-iris"
            >
              <option value="custom" className="bg-[#101018]">— Custom HTML —</option>
              {templates.map((tpl) => (
                <option key={tpl.key} value={tpl.key} className="bg-[#101018]">
                  {tpl.name} (v{tpl.version || 1})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Subject line */}
        <div>
          <label className="block text-[11px] text-fog mb-1.5 font-medium">EMAIL SUBJECT LINE *</label>
          <Input
            id="campaign-subject-input"
            placeholder="e.g. Important Advisory & Strategy Update — Navigatte"
            value={emailSubject}
            onChange={(e) => { setEmailSubject(e.target.value); setServerPreview(null); }}
            className="bg-white/5 border-white/10 text-cloud text-xs h-9"
          />
        </div>

        {/* Variable toolbar */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] text-iris flex items-center gap-1 font-mono uppercase shrink-0">
            <Sparkles className="w-3 h-3" /> Variables:
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
          {unresolvedVars.length > 0 && (
            <div className="ml-2 flex items-center gap-1 text-amber-400 text-[10px] font-mono">
              <AlertTriangle className="w-3 h-3" />
              Unresolved: {unresolvedVars.join(", ")}
            </div>
          )}
        </div>

        {/* 2-Pane: Editor + Preview */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-1">
          {/* LEFT: HTML Editor */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-fog">
              <span className="font-mono flex items-center gap-1.5">
                <FileCode className="w-3.5 h-3.5 text-iris" />
                HTML BODY
              </span>
              <span className="text-[10px] text-fog/60 font-mono">Authored HTML → sent as-is</span>
            </div>
            <textarea
              ref={textareaRef}
              rows={18}
              value={emailHtml}
              onChange={(e) => { setEmailHtml(e.target.value); setServerPreview(null); }}
              className="w-full bg-[#0a0a0f] border border-white/10 rounded-xl p-3 text-xs text-cloud font-mono outline-none focus:border-iris/60 resize-y leading-relaxed transition-all"
              spellCheck={false}
              aria-label="HTML email body editor"
            />
          </div>

          {/* RIGHT: Live Preview */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-fog">
              <div className="flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-mono">LIVE PREVIEW</span>
                {serverPreview && (
                  <span className="text-[9px] font-mono bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded-full border border-emerald-500/30">
                    SERVER RENDERED
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <div className="flex items-center gap-0.5 bg-white/5 p-0.5 rounded border border-white/10 mr-2">
                  <button
                    onClick={() => setPreviewViewport("desktop")}
                    className={`p-1 rounded text-[10px] flex items-center gap-1 transition-all ${previewViewport === "desktop" ? "bg-iris text-white" : "text-fog hover:text-cloud"}`}
                  >
                    <Monitor className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => setPreviewViewport("mobile")}
                    className={`p-1 rounded text-[10px] flex items-center gap-1 transition-all ${previewViewport === "mobile" ? "bg-iris text-white" : "text-fog hover:text-cloud"}`}
                  >
                    <Smartphone className="w-3 h-3" />
                  </button>
                </div>
                <button
                  onClick={handleFetchServerPreview}
                  disabled={loadingPreview}
                  className="text-[10px] text-iris hover:text-iris/80 font-mono flex items-center gap-1"
                  title="Fetch server-side render (same as outbox)"
                >
                  {loadingPreview ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  {loadingPreview ? "Rendering…" : "Server Render"}
                </button>
              </div>
            </div>

            {/* Subject preview line */}
            <div className="bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 flex items-center gap-2">
              <span className="text-[10px] text-fog font-mono shrink-0">SUBJ:</span>
              <span className="text-[11px] text-cloud truncate">{previewSubject || "—"}</span>
            </div>

            <div
              className={`border border-white/10 rounded-xl overflow-hidden bg-white shadow-inner mx-auto transition-all ${
                previewViewport === "mobile" ? "max-w-[400px]" : "w-full"
              }`}
            >
              <iframe
                srcDoc={previewHtml}
                title="Email preview"
                sandbox="allow-same-origin"
                className="w-full border-0"
                style={{ height: "380px" }}
              />
            </div>

            <p className="text-[10px] text-fog/50 font-mono text-center">
              Showing sample variables — actual recipient names used on send
            </p>
          </div>
        </div>
      </div>

      {/* ── Recipients Section ──────────────────────────────────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
        <span className="text-xs font-mono uppercase tracking-wider text-fog">Recipients</span>

        {/* Audience Source */}
        <div className="grid grid-cols-3 gap-2">
          {AUDIENCE_SOURCES.map((src) => (
            <button
              key={src.id}
              onClick={() => setAudienceSource(src.id)}
              className={`p-3 rounded-xl border text-left transition-all ${
                audienceSource === src.id
                  ? "bg-iris/15 border-iris/40 text-cloud"
                  : "bg-white/[0.02] border-white/10 text-fog hover:bg-white/[0.04]"
              }`}
            >
              <div className="text-xs font-medium text-cloud">{src.label}</div>
              <p className="text-[10px] text-fog mt-0.5">{src.desc}</p>
            </button>
          ))}
        </div>

        {/* Audience dropdown */}
        {(audienceSource === "audience" || audienceSource === "both") && (
          <div>
            <label className="block text-[11px] text-fog mb-1.5 font-medium">SELECT AUDIENCE LIST</label>
            <select
              value={selectedAudienceId}
              onChange={(e) => setSelectedAudienceId(e.target.value)}
              className="w-full h-9 text-xs bg-white/5 border border-white/10 text-cloud rounded-lg px-2.5 outline-none font-mono focus:border-iris"
            >
              <option value="" className="bg-[#101018]">— No audience selected —</option>
              {audiences.map((aud) => (
                <option key={aud.id} value={aud.id} className="bg-[#101018]">
                  {aud.name} ({aud.member_count || 0} members)
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Manual recipients chips */}
        {(audienceSource === "manual" || audienceSource === "both") && (
          <div>
            <label className="block text-[11px] text-fog mb-1.5 font-medium">
              MANUAL RECIPIENTS <span className="text-fog/50">(comma/Enter to add)</span>
            </label>
            <RecipientChips
              values={manualRecipients}
              onChange={setManualRecipients}
              placeholder="client@enterprise.com, partner@corp.io…"
              maxChips={500}
            />
          </div>
        )}

        {/* Exclusions */}
        <div>
          <label className="block text-[11px] text-fog mb-1.5 font-medium">
            EXCLUSIONS <span className="text-fog/50">(email or @domain)</span>
          </label>
          <div className="flex gap-2 mb-2">
            <Input
              value={exclusionInput}
              onChange={(e) => setExclusionInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addExclusion()}
              placeholder="@navigatte.com or specific@email.com"
              className="bg-white/5 border-white/10 text-cloud text-xs h-8 flex-1 font-mono"
            />
            <Button
              size="sm"
              onClick={addExclusion}
              variant="outline"
              className="border-white/10 text-fog hover:text-cloud hover:bg-white/5 h-8 text-xs"
            >
              <Plus className="w-3 h-3" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {exclusions.map((excl) => (
              <span
                key={excl}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono bg-rose-500/15 border border-rose-500/30 text-rose-300"
              >
                {excl}
                <button onClick={() => setExclusions(exclusions.filter((e) => e !== excl))}>
                  <X className="w-2.5 h-2.5 hover:text-rose-200" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Recipient Breakdown */}
        <div className="p-3 bg-black/40 border border-white/10 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-xs text-cloud font-medium">
              <Users className="w-3.5 h-3.5 text-iris" />
              Recipient Breakdown
            </div>
            <button
              onClick={handleCalculateBreakdown}
              disabled={loadingBreakdown}
              className="text-[10px] text-iris hover:text-iris/80 font-mono flex items-center gap-1"
            >
              {loadingBreakdown ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              {loadingBreakdown ? "Calculating…" : "Calculate"}
            </button>
          </div>

          {recipientBreakdown ? (
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              <div className="text-center">
                <div className="text-base font-bold text-cloud">{recipientBreakdown.raw_count}</div>
                <div className="text-[10px] text-fog">Raw</div>
              </div>
              <div className="text-center">
                <div className="text-base font-bold text-amber-400">{recipientBreakdown.suppressed_count}</div>
                <div className="text-[10px] text-fog">Suppressed</div>
              </div>
              <div className="text-center">
                <div className="text-base font-bold text-rose-400">{recipientBreakdown.excluded_count}</div>
                <div className="text-[10px] text-fog">Excluded</div>
              </div>
              <div className="col-span-3 pt-1 border-t border-white/10 text-center">
                <span className="text-fog text-[11px]">Final Deliverable: </span>
                <span className="text-emerald-400 font-bold text-sm">{recipientBreakdown.final_count}</span>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-fog/60 font-mono text-center py-1">
              Click Calculate to see recipient breakdown
            </p>
          )}
        </div>
      </div>

      {/* ── Test Section ────────────────────────────────────────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-mono uppercase tracking-wider text-fog">Test Send</span>
          <span className="text-[10px] text-fog/60 font-mono">(never sends to audience)</span>
        </div>

        <div>
          <label className="block text-[11px] text-fog mb-1.5 font-medium">
            TEST RECIPIENTS <span className="text-fog/50">(server-enforced — audience contacts blocked)</span>
          </label>
          <RecipientChips
            values={testRecipients}
            onChange={setTestRecipients}
            placeholder="test@navigatte.com…"
            maxChips={10}
          />
        </div>

        <Button
          id="send-test-btn"
          onClick={handleSendTest}
          disabled={sendingTest || testRecipients.length === 0}
          variant="outline"
          className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 h-9 text-xs rounded-lg"
        >
          {sendingTest ? (
            <>
              <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
              Sending Test…
            </>
          ) : (
            <>
              <Send className="w-3.5 h-3.5 mr-2" />
              Send Test to {testRecipients.length > 0 ? `${testRecipients.length} Recipient${testRecipients.length > 1 ? "s" : ""}` : "Test Recipients"}
            </>
          )}
        </Button>
      </div>

      {/* ── Launch Bar ─────────────────────────────────────────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-4 flex flex-wrap items-center gap-3">
        <Button
          id="save-draft-btn"
          onClick={() => handleSaveDraft(false)}
          disabled={savingDraft}
          variant="outline"
          className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 h-9 text-xs rounded-lg"
        >
          {savingDraft ? (
            <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />Saving…</>
          ) : (
            <><Save className="w-3.5 h-3.5 mr-2" />Save Draft</>
          )}
        </Button>

        <Button
          id="render-preview-btn"
          onClick={handleFetchServerPreview}
          disabled={loadingPreview}
          variant="outline"
          className="border-iris/30 text-iris hover:bg-iris/10 h-9 text-xs rounded-lg"
        >
          {loadingPreview ? (
            <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />Rendering…</>
          ) : (
            <><Eye className="w-3.5 h-3.5 mr-2" />Render Preview</>
          )}
        </Button>

        <Button
          id="review-launch-btn"
          onClick={handleOpenLaunch}
          disabled={validating || launching}
          className={`h-9 text-xs rounded-lg font-semibold ml-auto ${
            isProductionMode
              ? "bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-900/30"
              : "bg-iris hover:bg-iris/90 text-white"
          }`}
        >
          {validating ? (
            <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />Validating…</>
          ) : (
            <><Zap className="w-3.5 h-3.5 mr-2" />Review &amp; Launch</>
          )}
        </Button>
      </div>

      {/* ── Production Safety Modal ─────────────────────────────────────── */}
      <ProductionSafetyModal
        open={safetyModalOpen}
        onClose={() => setSafetyModalOpen(false)}
        onConfirm={handleConfirmLaunch}
        loading={launching}
        campaign={{ name: campTitle, subject: emailSubject, environment }}
        checklist={launchChecklist}
        previewHtml={launchPreviewHtml || previewHtml}
        previewSubject={previewSubject}
        diagnostics={diagnostics}
      />
    </>
  );
};

export default CampaignStudio;
