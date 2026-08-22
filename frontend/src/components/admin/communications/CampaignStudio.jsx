/**
 * CampaignStudio — One-Screen Email Campaign Composer
 *
 * This component is the primary creative and operational studio for all email campaigns:
 *
 * Core Workflow:
 *   1. Compose (Template or Custom HTML with Live Variables Toolbar)
 *   2. Real-time Live Preview (Sandboxed iframe, instant variable interpolation)
 *   3. Recipients (Audience Only, Manual Only with Direct CSV/XLSX Import, or Both)
 *   4. Safety Environment Toggle (TEST Mode vs PRODUCTION Mode)
 *   5. Test Send (One-click real Resend dispatch to test recipients with instant feedback)
 *   6. Review & Launch (Exact recipient breakdown + safety count-confirmation modal)
 *
 * Architectural Invariant:
 *   Preview Shown == Test Sent == Outbox Snapshot == Delivered Broadcast
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
  Upload,
  FileSpreadsheet,
  AlertCircle,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";
import { RecipientChips } from "./RecipientChips";
import { ProductionSafetyModal } from "./ProductionSafetyModal";

// Variable toolbar tokens with human explanations
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

const AUTOSAVE_DEBOUNCE_MS = 25000;
const LOCAL_SAVE_DEBOUNCE_MS = 1500;

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
 * Replaces placeholders with realistic preview data
 */
function buildPreviewHtml(html) {
  let rendered = html || "";
  Object.entries(SAMPLE_VARS).forEach(([k, v]) => {
    rendered = rendered.split(k).join(v);
  });
  return rendered;
}

/**
 * Detects any {{ var }} placeholders remaining in content
 */
function detectUnresolvedVars(html) {
  const matches = (html || "").match(/\{\{\s*\w+\s*\}\}/g) || [];
  return [...new Set(matches)];
}

/**
 * Client-side parser for CSV/text lines with email extraction
 */
function parseCsvContent(text) {
  const lines = text.split(/[\r\n]+/).map((l) => l.trim()).filter(Boolean);
  const validEmails = [];
  let invalidCount = 0;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  lines.forEach((line) => {
    // Check if comma/tab separated
    const parts = line.split(/[,\t;]/).map((p) => p.replace(/["']/g, "").trim());
    const foundEmail = parts.find((p) => emailRegex.test(p));
    if (foundEmail) {
      validEmails.push(foundEmail.toLowerCase());
    } else {
      invalidCount++;
    }
  });

  const uniqueEmails = [...new Set(validEmails)];
  const duplicateCount = validEmails.length - uniqueEmails.length;

  return {
    totalRows: lines.length,
    validEmails: uniqueEmails,
    validCount: uniqueEmails.length,
    duplicateCount,
    invalidCount,
  };
}

export const CampaignStudio = ({
  templates = [],
  audiences = [],
  suppressions = [],
  diagnostics = null,
  initialCampaign = null,
  onCampaignSaved = () => {},
  onCampaignLaunched = () => {},
}) => {
  const { toast } = useToast();
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const autosaveTimerRef = useRef(null);
  const localSaveTimerRef = useRef(null);

  // ── Campaign Identity & Environment ───────────────────────────────────────
  const [campId, setCampId] = useState(initialCampaign?.id || null);
  const [campTitle, setCampTitle] = useState(initialCampaign?.name || "");
  const [campaignEnv, setCampaignEnv] = useState(initialCampaign?.environment || "test"); // 'test' | 'production'
  const [autosaveStatus, setAutosaveStatus] = useState("idle"); // idle | saving | saved | error

  // ── Email Content ────────────────────────────────────────────────────────
  const [selectedTemplateKey, setSelectedTemplateKey] = useState(initialCampaign?.template_key || "custom");
  const [emailSubject, setEmailSubject] = useState(initialCampaign?.subject || "");
  const [emailHtml, setEmailHtml] = useState(initialCampaign?.custom_html || DEFAULT_HTML);
  const [hasCustomEdits, setHasCustomEdits] = useState(false);

  // ── Preview State ────────────────────────────────────────────────────────
  const [previewViewport, setPreviewViewport] = useState("desktop");

  // ── Recipients ───────────────────────────────────────────────────────────
  const [audienceSource, setAudienceSource] = useState(
    initialCampaign?.audience_source || "manual"
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

  // ── Manual Import Modal ──────────────────────────────────────────────────
  const [manualImportModalOpen, setManualImportModalOpen] = useState(false);
  const [manualImportSummary, setManualImportSummary] = useState(null);
  const [manualImportPastedText, setManualImportPastedText] = useState("");
  const [importTab, setImportTab] = useState("file"); // 'file' | 'paste'

  // ── Test Section ─────────────────────────────────────────────────────────
  const [testRecipients, setTestRecipients] = useState(
    initialCampaign?.test_recipients || ["ishanchauhan2001@gmail.com"]
  );
  const [sendingTest, setSendingTest] = useState(false);
  const [lastTestResult, setLastTestResult] = useState(null);

  // ── Launch Flow ──────────────────────────────────────────────────────────
  const [savingDraft, setSavingDraft] = useState(false);
  const [validating, setValidating] = useState(false);
  const [safetyModalOpen, setSafetyModalOpen] = useState(false);
  const [launchChecklist, setLaunchChecklist] = useState(null);
  const [launching, setLaunching] = useState(false);

  // ── Derived State ────────────────────────────────────────────────────────
  const isTestMode = campaignEnv === "test";
  const fromEmail = diagnostics?.provider?.from_email || "Navigatte <updates@updates.navigatte.com>";
  const previewHtml = buildPreviewHtml(emailHtml);
  const previewSubject = buildPreviewHtml(emailSubject);
  const unresolvedVars = detectUnresolvedVars(previewHtml);

  // Sync when initialCampaign changes (e.g. "Load into Composer" clicked)
  useEffect(() => {
    if (initialCampaign) {
      setCampId(initialCampaign.id || null);
      setCampTitle(initialCampaign.name || "");
      setCampaignEnv(initialCampaign.environment || "test");
      setSelectedTemplateKey(initialCampaign.template_key || "custom");
      setEmailSubject(initialCampaign.subject || "");
      if (initialCampaign.custom_html) setEmailHtml(initialCampaign.custom_html);
      if (initialCampaign.manual_recipients) setManualRecipients(initialCampaign.manual_recipients);
      if (initialCampaign.test_recipients) setTestRecipients(initialCampaign.test_recipients);
      if (initialCampaign.exclusions) setExclusions(initialCampaign.exclusions);
      if (initialCampaign.audience_id) setSelectedAudienceId(initialCampaign.audience_id);
      if (initialCampaign.audience_source) setAudienceSource(initialCampaign.audience_source);
    }
  }, [initialCampaign]);

  // ── Local Storage Draft Caching ──────────────────────────────────────────
  useEffect(() => {
    if (!campId) return;
    try {
      const saved = localStorage.getItem(`campaign_draft_${campId}`);
      if (saved) {
        const d = JSON.parse(saved);
        if (d.emailHtml && !initialCampaign) setEmailHtml(d.emailHtml);
        if (d.emailSubject && !initialCampaign) setEmailSubject(d.emailSubject);
      }
    } catch (e) { /* ignore */ }
  }, [campId, initialCampaign]);

  const saveToLocalStorage = useCallback(() => {
    if (!campId) return;
    try {
      localStorage.setItem(`campaign_draft_${campId}`, JSON.stringify({
        emailHtml, emailSubject, campTitle, campaignEnv, savedAt: Date.now(),
      }));
    } catch (e) { /* ignore */ }
  }, [campId, emailHtml, emailSubject, campTitle, campaignEnv]);

  useEffect(() => {
    clearTimeout(localSaveTimerRef.current);
    localSaveTimerRef.current = setTimeout(saveToLocalStorage, LOCAL_SAVE_DEBOUNCE_MS);
    return () => clearTimeout(localSaveTimerRef.current);
  }, [emailHtml, emailSubject, campTitle, campaignEnv, saveToLocalStorage]);

  // ── Template Selection with Protection ───────────────────────────────────
  const handleTemplateSelect = (key) => {
    if (key === selectedTemplateKey) return;

    if (hasCustomEdits && key !== "custom") {
      const ok = window.confirm("Loading this template will replace your current email HTML and subject. Proceed?");
      if (!ok) return;
    }

    setSelectedTemplateKey(key);
    if (key !== "custom") {
      const tpl = templates.find((t) => t.key === key);
      if (tpl) {
        setEmailSubject(tpl.subject || "");
        setEmailHtml(tpl.body_html || "");
        setHasCustomEdits(false);
      }
    }
  };

  // ── Variable Placeholder Insertion ───────────────────────────────────────
  const handleInsertPlaceholder = (placeholder) => {
    if (!textareaRef.current) {
      setEmailHtml((prev) => prev + " " + placeholder);
      return;
    }
    const start = textareaRef.current.selectionStart;
    const end = textareaRef.current.selectionEnd;
    const updated = emailHtml.substring(0, start) + placeholder + emailHtml.substring(end);
    setEmailHtml(updated);
    setHasCustomEdits(true);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const pos = start + placeholder.length;
        textareaRef.current.selectionStart = textareaRef.current.selectionEnd = pos;
      }
    }, 50);
  };

  // ── Campaign Payload Builder ─────────────────────────────────────────────
  const getCampaignPayload = useCallback(() => ({
    name: campTitle.trim() || "Untitled Campaign",
    environment: campaignEnv,
    subject: emailSubject || "Navigatte Communication",
    template_key: selectedTemplateKey,
    audience_id: selectedAudienceId || null,
    audience_source: audienceSource,
    manual_recipients: manualRecipients,
    exclusions,
    custom_html: emailHtml,
    test_recipients: testRecipients,
  }), [campTitle, campaignEnv, emailSubject, selectedTemplateKey, selectedAudienceId,
       audienceSource, manualRecipients, exclusions, emailHtml, testRecipients]);

  // ── Save Draft ───────────────────────────────────────────────────────────
  const handleSaveDraft = useCallback(async (silent = false) => {
    if (!campTitle.trim() && !silent) {
      toast({ variant: "destructive", title: "Campaign name required", description: "Please enter a campaign name before saving." });
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
        toast({ title: "Draft Saved", description: `Campaign '${payload.name}' saved.` });
        onCampaignSaved(id);
      }
      setTimeout(() => setAutosaveStatus("idle"), 3000);
      return id;
    } catch (err) {
      setAutosaveStatus("error");
      if (!silent) {
        toast({ variant: "destructive", title: "Save Failed", description: err.response?.data?.detail || err.message });
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
  }, [emailHtml, emailSubject, campTitle, campaignEnv, manualRecipients, testRecipients, exclusions, campId, handleSaveDraft]);

  // ── Recipient Calculation ────────────────────────────────────────────────
  const handleCalculateRecipients = async () => {
    let id = campId;
    if (!id) {
      id = await handleSaveDraft(false);
      if (!id) return;
    } else {
      await handleSaveDraft(true);
    }

    setLoadingBreakdown(true);
    try {
      const resp = await api.post(`/admin/communications/campaigns/${id}/calculate-recipients`);
      setRecipientBreakdown(resp.data);
    } catch (err) {
      toast({ variant: "destructive", title: "Calculation Failed", description: err.response?.data?.detail || err.message });
    } finally {
      setLoadingBreakdown(false);
    }
  };

  // ── Unified Test Send (Single Canonical Endpoint) ─────────────────────────
  const handleSendTest = async () => {
    if (testRecipients.length === 0) {
      toast({ variant: "destructive", title: "No Test Recipients", description: "Add at least one test recipient email." });
      return;
    }
    if (!emailSubject.trim()) {
      toast({ variant: "destructive", title: "Subject Line Required", description: "Please enter an email subject line before sending." });
      return;
    }

    setSendingTest(true);
    setLastTestResult(null);

    try {
      // Auto-save draft silently in background
      handleSaveDraft(true);

      // Call single canonical /send-test endpoint (works on all environments)
      const resp = await api.post("/admin/communications/send-test", {
        recipient_emails: testRecipients,
        subject: emailSubject,
        custom_html: selectedTemplateKey === "custom" ? emailHtml : null,
        template_key: selectedTemplateKey !== "custom" ? selectedTemplateKey : null,
        variables: SAMPLE_VARS,
      });

      setLastTestResult(resp.data);

      if (resp.data.success) {
        toast({
          title: "Test Dispatched ✓",
          description: `Dispatched to ${resp.data.sent_count}/${resp.data.total_recipients || testRecipients.length} test recipient(s).`,
        });
      } else {
        toast({
          variant: "destructive",
          title: resp.data.status === "provider_disabled" ? "Provider Not Ready" : "Test Send Failed",
          description: resp.data.error_message || "Could not deliver test email.",
        });
      }
    } catch (err) {
      const is404 = err.response?.status === 404;
      const errorMsg = is404
        ? "The communications service is currently reconciling deployment. Please verify backend connectivity."
        : err.response?.data?.detail || err.message;

      setLastTestResult({
        success: false,
        status: "error",
        error_message: errorMsg,
      });

      toast({
        variant: "destructive",
        title: "Test Send Error",
        description: errorMsg,
      });
    } finally {
      setSendingTest(false);
    }
  };

  // ── Review & Launch Flow ──────────────────────────────────────────────────
  const handleOpenLaunch = async () => {
    if (!campTitle.trim()) {
      toast({ variant: "destructive", title: "Campaign Name Required" });
      return;
    }
    if (!emailSubject.trim()) {
      toast({ variant: "destructive", title: "Subject Line Required" });
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

      const valResp = await api.get(`/admin/communications/campaigns/${id}/validate`);
      const validation = valResp.data;

      if (!validation.is_valid) {
        toast({
          variant: "destructive",
          title: "Pre-Flight Validation Blocked",
          description: validation.errors?.join(". ") || "Fix blocking errors before launching.",
        });
        return;
      }

      setLaunchChecklist(validation.checklist);
      setSafetyModalOpen(true);
    } catch (err) {
      toast({ variant: "destructive", title: "Validation Error", description: err.response?.data?.detail || err.message });
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
        description: resp.data.message || `Campaign queued for ${resp.data.campaign?.total_recipients} recipient(s).`,
      });
      onCampaignLaunched(campId);
    } catch (err) {
      toast({ variant: "destructive", title: "Launch Failed", description: err.response?.data?.detail || err.message });
    } finally {
      setLaunching(false);
    }
  };

  // ── Direct Manual Recipient Import (CSV / XLSX) ──────────────────────────
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target.result;
      const parsed = parseCsvContent(content);
      setManualImportSummary({
        filename: file.name,
        ...parsed,
      });
    };
    reader.readAsText(file);
  };

  const handlePasteParse = () => {
    if (!manualImportPastedText.trim()) return;
    const parsed = parseCsvContent(manualImportPastedText);
    setManualImportSummary({
      filename: "Pasted text",
      ...parsed,
    });
  };

  const handleApplyManualImport = () => {
    if (!manualImportSummary || !manualImportSummary.validEmails) return;

    const existingSet = new Set(manualRecipients.map((e) => e.toLowerCase()));
    const newEmails = manualImportSummary.validEmails.filter((e) => !existingSet.has(e));

    setManualRecipients([...manualRecipients, ...newEmails]);
    toast({
      title: "Recipients Imported",
      description: `Added ${newEmails.length} verified email recipient(s) to manual list.`,
    });

    setManualImportModalOpen(false);
    setManualImportSummary(null);
    setManualImportPastedText("");
  };

  // ── Exclusions Helper ────────────────────────────────────────────────────
  const addExclusion = () => {
    const val = exclusionInput.trim().toLowerCase();
    if (!val || exclusions.includes(val)) return;
    setExclusions([...exclusions, val]);
    setExclusionInput("");
  };

  return (
    <div className="space-y-6">
      {/* ── Section 1: Campaign Identity & Environment Mode ───────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4 shadow-sm">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          {/* Campaign Name */}
          <div className="w-full lg:flex-1">
            <label className="block text-[11px] text-fog mb-1 font-mono uppercase tracking-wider">
              Campaign Name
            </label>
            <Input
              id="campaign-name-input"
              value={campTitle}
              onChange={(e) => setCampTitle(e.target.value)}
              placeholder="e.g. Q3 Technical Advisory & Regulatory Briefing"
              className="bg-white/5 border-white/10 text-cloud text-sm h-10 font-medium"
            />
          </div>

          {/* Real Environment Mode Selector */}
          <div className="w-full lg:w-auto shrink-0 space-y-1">
            <label className="block text-[11px] text-fog font-mono uppercase tracking-wider">
              Dispatch Mode
            </label>
            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/5 border border-white/10">
              <button
                type="button"
                onClick={() => setCampaignEnv("test")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all ${
                  isTestMode
                    ? "bg-emerald-600 text-white shadow-md shadow-emerald-950/50"
                    : "text-fog hover:text-cloud hover:bg-white/5"
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                TEST MODE
              </button>

              <button
                type="button"
                onClick={() => setCampaignEnv("production")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all ${
                  !isTestMode
                    ? "bg-rose-600 text-white shadow-md shadow-rose-950/50"
                    : "text-fog hover:text-cloud hover:bg-white/5"
                }`}
              >
                <Zap className="w-3.5 h-3.5" />
                PRODUCTION
              </button>
            </div>
          </div>
        </div>

        {/* Environment Safety Notification Banner */}
        <div className={`p-3.5 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs transition-colors ${
          isTestMode
            ? "bg-emerald-950/25 border-emerald-500/30 text-emerald-300"
            : "bg-rose-950/25 border-rose-500/30 text-rose-300"
        }`}>
          <div className="flex items-center gap-2 font-medium">
            {isTestMode ? <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" /> : <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />}
            <span>
              {isTestMode
                ? "TEST MODE: Emails will be strictly dispatched ONLY to configured test recipients. Audience lists are blocked."
                : "PRODUCTION MODE: Live broadcast mode. Audience recipients and safety confirmation will be required."}
            </span>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px] shrink-0">
            <span>From: <strong className="text-cloud">{fromEmail}</strong></span>
            {autosaveStatus === "saving" && <span className="text-iris animate-pulse">Autosaving…</span>}
            {autosaveStatus === "saved" && <span className="text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" /> Saved</span>}
          </div>
        </div>
      </div>

      {/* ── Section 2: Email Content Editor + Real-time Live Preview ───────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <span className="text-xs font-mono uppercase tracking-wider text-fog">Email Content</span>
            <p className="text-[11px] text-fog/70 mt-0.5">Author custom HTML or select a template. What you see in preview is exactly what is sent.</p>
          </div>

          {/* Template Picker */}
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

        {/* Email Subject */}
        <div>
          <label className="block text-[11px] text-fog mb-1.5 font-medium">EMAIL SUBJECT LINE *</label>
          <Input
            id="campaign-subject-input"
            placeholder="e.g. Important Regulatory & Strategy Briefing — Navigatte"
            value={emailSubject}
            onChange={(e) => {
              setEmailSubject(e.target.value);
              setHasCustomEdits(true);
            }}
            className="bg-white/5 border-white/10 text-cloud text-xs h-9"
          />
        </div>

        {/* Variables Toolbar */}
        <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
          <span className="text-[10px] text-iris flex items-center gap-1 font-mono uppercase shrink-0">
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
          {unresolvedVars.length > 0 && (
            <div className="ml-auto flex items-center gap-1 text-amber-400 text-[10px] font-mono">
              <AlertTriangle className="w-3 h-3" />
              Unresolved: {unresolvedVars.join(", ")}
            </div>
          )}
        </div>

        {/* 2-Pane Editor & Real-Time Preview */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-1">
          {/* Left Pane: HTML Editor */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-fog">
              <span className="font-mono flex items-center gap-1.5">
                <FileCode className="w-3.5 h-3.5 text-iris" /> HTML BODY
              </span>
              <span className="text-[10px] text-fog/60 font-mono">Exact HTML sent to recipients</span>
            </div>
            <textarea
              ref={textareaRef}
              rows={18}
              value={emailHtml}
              onChange={(e) => {
                setEmailHtml(e.target.value);
                setHasCustomEdits(true);
              }}
              className="w-full bg-[#0a0a0f] border border-white/10 rounded-xl p-3 text-xs text-cloud font-mono outline-none focus:border-iris/60 resize-y leading-relaxed"
              spellCheck={false}
              aria-label="HTML email editor"
            />
          </div>

          {/* Right Pane: Real-Time Preview (Sandboxed iframe) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-fog">
              <div className="flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-mono">LIVE PREVIEW</span>
              </div>

              {/* Viewport switcher */}
              <div className="flex items-center gap-0.5 bg-white/5 p-0.5 rounded border border-white/10">
                <button
                  type="button"
                  onClick={() => setPreviewViewport("desktop")}
                  className={`px-2 py-0.5 rounded text-[10px] flex items-center gap-1 transition-all ${
                    previewViewport === "desktop" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                  }`}
                >
                  <Monitor className="w-2.5 h-2.5" /> Desktop
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewViewport("mobile")}
                  className={`px-2 py-0.5 rounded text-[10px] flex items-center gap-1 transition-all ${
                    previewViewport === "mobile" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                  }`}
                >
                  <Smartphone className="w-2.5 h-2.5" /> Mobile
                </button>
              </div>
            </div>

            {/* Subject Preview Line */}
            <div className="bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 flex items-center gap-2">
              <span className="text-[10px] text-fog font-mono shrink-0">SUBJECT:</span>
              <span className="text-[11px] text-cloud truncate font-medium">{previewSubject || "—"}</span>
            </div>

            {/* Live Rendered Iframe */}
            <div
              className={`border border-white/10 rounded-xl overflow-hidden bg-white shadow-inner mx-auto transition-all ${
                previewViewport === "mobile" ? "max-w-[380px]" : "w-full"
              }`}
            >
              <iframe
                srcDoc={previewHtml}
                title="Live email preview"
                sandbox="allow-same-origin"
                className="w-full border-0"
                style={{ height: "370px" }}
              />
            </div>

            <p className="text-[10px] text-fog/50 font-mono text-center">
              Preview renders sample variables — actual recipient attributes used on send
            </p>
          </div>
        </div>
      </div>

      {/* ── Section 3: Test Recipients & Instant Test Send ────────────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono uppercase tracking-wider text-fog">Test Dispatch</span>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
              Safe Sandbox
            </span>
          </div>
          <span className="text-[11px] text-fog">Dispatches real emails to test addresses only</span>
        </div>

        <div>
          <label className="block text-[11px] text-fog mb-1.5 font-medium">
            TEST RECIPIENT(S) <span className="text-fog/50">(Comma/Enter to add)</span>
          </label>
          <RecipientChips
            values={testRecipients}
            onChange={setTestRecipients}
            placeholder="test@navigatte.com, admin@enterprise.com…"
            maxChips={10}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            id="send-test-btn"
            onClick={handleSendTest}
            disabled={sendingTest || testRecipients.length === 0}
            className="bg-emerald-600 hover:bg-emerald-500 text-white h-9 text-xs px-4 rounded-lg font-medium shadow-md shadow-emerald-950/40"
          >
            {sendingTest ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                Sending Test…
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5 mr-2" />
                Send Test Email → ({testRecipients.length} Recipient{testRecipients.length > 1 ? "s" : ""})
              </>
            )}
          </Button>

          {lastTestResult && (
            <div className={`p-2 px-3 rounded-lg border text-xs flex items-center gap-2 font-mono ${
              lastTestResult.success
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                : "bg-rose-500/10 border-rose-500/30 text-rose-300"
            }`}>
              {lastTestResult.success ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Accepted by Resend (Message ID: {lastTestResult.provider_message_id || lastTestResult.results?.[0]?.message_id || "sent"})</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                  <span>{lastTestResult.error_message || "Test dispatch failed"}</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Section 4: Campaign Recipients & Direct CSV/XLSX Import ────────── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono uppercase tracking-wider text-fog">Campaign Target Audience</span>
          <span className="text-[11px] text-fog font-mono">
            {isTestMode ? "Configured for upcoming production launch" : "Active targets for live broadcast"}
          </span>
        </div>

        {/* Audience Source Selector */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {[
            { id: "manual", label: "Manual Only", desc: "Chips & direct CSV/XLSX import" },
            { id: "audience", label: "Audience Only", desc: "Saved audience list members" },
            { id: "both", label: "Audience + Manual", desc: "Merged and deduplicated" },
          ].map((src) => (
            <button
              key={src.id}
              type="button"
              onClick={() => setAudienceSource(src.id)}
              className={`p-3 rounded-xl border text-left transition-all ${
                audienceSource === src.id
                  ? "bg-iris/15 border-iris/40 text-cloud"
                  : "bg-white/[0.02] border-white/10 text-fog hover:bg-white/[0.04]"
              }`}
            >
              <div className="text-xs font-semibold text-cloud">{src.label}</div>
              <p className="text-[10px] text-fog mt-0.5">{src.desc}</p>
            </button>
          ))}
        </div>

        {/* Audience Selector Dropdown */}
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

        {/* Manual Recipients with Direct CSV/XLSX Import */}
        {(audienceSource === "manual" || audienceSource === "both") && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-[11px] text-fog font-medium">
                MANUAL RECIPIENT LIST <span className="text-fog/50">({manualRecipients.length} recipients)</span>
              </label>

              {/* Direct CSV / XLSX Import Trigger */}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setManualImportModalOpen(true)}
                className="border-iris/40 text-iris hover:bg-iris/10 text-[11px] h-7 px-2.5"
              >
                <FileSpreadsheet className="w-3 h-3 mr-1.5" />
                Import CSV / XLSX
              </Button>
            </div>

            <RecipientChips
              values={manualRecipients}
              onChange={setManualRecipients}
              placeholder="Paste or type recipient email addresses…"
              maxChips={5000}
            />
          </div>
        )}

        {/* Exclusions */}
        <div>
          <label className="block text-[11px] text-fog mb-1.5 font-medium">
            CAMPAIGN EXCLUSIONS <span className="text-fog/50">(Email address or @domain to exclude)</span>
          </label>
          <div className="flex gap-2 mb-2">
            <Input
              value={exclusionInput}
              onChange={(e) => setExclusionInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addExclusion())}
              placeholder="@navigatte.com or specific@email.com"
              className="bg-white/5 border-white/10 text-cloud text-xs h-8 flex-1 font-mono"
            />
            <Button
              type="button"
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
                <button type="button" onClick={() => setExclusions(exclusions.filter((e) => e !== excl))}>
                  <X className="w-2.5 h-2.5 hover:text-rose-200" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Recipient Calculation Bar */}
        <div className="p-3.5 bg-black/40 border border-white/10 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-cloud font-medium">
              <Users className="w-3.5 h-3.5 text-iris" />
              Recipient Calculation &amp; Safety Audit
            </div>
            <button
              type="button"
              onClick={handleCalculateRecipients}
              disabled={loadingBreakdown}
              className="text-[10px] text-iris hover:text-iris/80 font-mono flex items-center gap-1"
            >
              {loadingBreakdown ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              {loadingBreakdown ? "Calculating…" : "Calculate Breakdown"}
            </button>
          </div>

          {recipientBreakdown ? (
            <div className="grid grid-cols-4 gap-2 text-xs font-mono pt-1 border-t border-white/5">
              <div className="bg-white/[0.02] p-2 rounded text-center">
                <div className="text-sm font-bold text-cloud">{recipientBreakdown.raw_count}</div>
                <div className="text-[10px] text-fog">Raw Total</div>
              </div>
              <div className="bg-white/[0.02] p-2 rounded text-center">
                <div className="text-sm font-bold text-amber-400">{recipientBreakdown.suppressed_count}</div>
                <div className="text-[10px] text-fog">Suppressed</div>
              </div>
              <div className="bg-white/[0.02] p-2 rounded text-center">
                <div className="text-sm font-bold text-rose-400">{recipientBreakdown.excluded_count}</div>
                <div className="text-[10px] text-fog">Excluded</div>
              </div>
              <div className="bg-emerald-950/30 border border-emerald-500/30 p-2 rounded text-center">
                <div className="text-sm font-bold text-emerald-400">{recipientBreakdown.final_count}</div>
                <div className="text-[10px] text-emerald-300">Net Deliverable</div>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-fog/60 font-mono text-center py-1">
              Click Calculate Breakdown to audit net deliverable recipients after suppression &amp; exclusions
            </p>
          )}
        </div>
      </div>

      {/* ── Section 5: Bottom Action Bar (Save Draft, Send Test, Launch) ──── */}
      <div className="bg-obsidian border border-white/10 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-2">
          <Button
            id="save-draft-btn"
            type="button"
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
            type="button"
            onClick={handleSendTest}
            disabled={sendingTest || testRecipients.length === 0}
            variant="outline"
            className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 h-9 text-xs rounded-lg font-mono"
          >
            <Send className="w-3.5 h-3.5 mr-1.5" />
            Send Test
          </Button>
        </div>

        <Button
          id="review-launch-btn"
          type="button"
          onClick={handleOpenLaunch}
          disabled={validating || launching}
          className={`h-9 text-xs px-6 rounded-lg font-semibold shadow-md ${
            !isTestMode
              ? "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/40"
              : "bg-iris hover:bg-iris/90 text-white shadow-iris/20"
          }`}
        >
          {validating ? (
            <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />Validating Pre-flight…</>
          ) : (
            <><Zap className="w-3.5 h-3.5 mr-2" />Review &amp; Launch {isTestMode ? "(Test)" : "(Production)"}</>
          )}
        </Button>
      </div>

      {/* ── Modal: Manual CSV/XLSX Recipient Import ──────────────────────── */}
      {manualImportModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-medium text-cloud">Import Manual Recipients</h3>
                <p className="text-xs text-fog mt-0.5">Upload a CSV/XLSX file or paste text containing email addresses.</p>
              </div>
              <button
                type="button"
                onClick={() => setManualImportModalOpen(false)}
                className="text-fog hover:text-cloud text-xs p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Import Mode Switcher */}
            <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-lg">
              <button
                type="button"
                onClick={() => setImportTab("file")}
                className={`py-1.5 text-xs font-medium rounded-md transition-all ${
                  importTab === "file" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                }`}
              >
                Upload File (CSV / XLSX)
              </button>
              <button
                type="button"
                onClick={() => setImportTab("paste")}
                className={`py-1.5 text-xs font-medium rounded-md transition-all ${
                  importTab === "paste" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                }`}
              >
                Paste Emails / Text
              </button>
            </div>

            {importTab === "file" ? (
              <div className="space-y-3">
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".csv,.xlsx,.xls,.txt"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-white/15 hover:border-iris/50 rounded-xl p-6 text-center cursor-pointer transition-all bg-white/[0.02]"
                >
                  <FileSpreadsheet className="w-8 h-8 text-iris mx-auto mb-2 opacity-80" />
                  <p className="text-xs text-cloud font-medium">Click to select CSV or XLSX file</p>
                  <p className="text-[10px] text-fog mt-0.5">Supports CSV, XLSX, XLS, TXT</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-xs">
                <label className="block text-fog">Paste text or CSV lines:</label>
                <textarea
                  rows={6}
                  value={manualImportPastedText}
                  onChange={(e) => setManualImportPastedText(e.target.value)}
                  placeholder={`client1@enterprise.com\nclient2@corp.io, Sarah Connor, Corp\npartner@tech.io`}
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2.5 text-xs text-cloud font-mono outline-none focus:border-iris resize-y"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handlePasteParse}
                  className="border-white/10 text-cloud text-xs h-7"
                >
                  Parse Pasted Content
                </Button>
              </div>
            )}

            {/* Import Summary Statistics */}
            {manualImportSummary && (
              <div className="p-3.5 bg-white/5 border border-white/10 rounded-xl space-y-2 text-xs font-mono">
                <div className="text-cloud font-semibold flex items-center justify-between">
                  <span>Parsed: {manualImportSummary.filename}</span>
                  <span className="text-emerald-400 font-bold">+{manualImportSummary.validCount} valid</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-[11px] pt-1">
                  <div className="bg-black/30 p-1.5 rounded">
                    <div className="text-cloud font-bold">{manualImportSummary.totalRows}</div>
                    <div className="text-fog text-[10px]">Total Rows</div>
                  </div>
                  <div className="bg-black/30 p-1.5 rounded">
                    <div className="text-amber-400 font-bold">{manualImportSummary.duplicateCount}</div>
                    <div className="text-fog text-[10px]">Duplicates</div>
                  </div>
                  <div className="bg-black/30 p-1.5 rounded">
                    <div className="text-rose-400 font-bold">{manualImportSummary.invalidCount}</div>
                    <div className="text-fog text-[10px]">Invalid</div>
                  </div>
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setManualImportModalOpen(false)}
                className="border-white/10 text-ash text-xs h-8"
              >
                Cancel
              </Button>
              <Button
                type="button"
                disabled={!manualImportSummary || manualImportSummary.validCount === 0}
                onClick={handleApplyManualImport}
                size="sm"
                className="bg-iris text-white text-xs h-8"
              >
                Add {manualImportSummary?.validCount || 0} Recipients to List
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Production Safety Confirmation ───────────────────────── */}
      <ProductionSafetyModal
        open={safetyModalOpen}
        onClose={() => setSafetyModalOpen(false)}
        onConfirm={handleConfirmLaunch}
        loading={launching}
        campaign={{ name: campTitle, subject: emailSubject, environment: campaignEnv }}
        checklist={launchChecklist}
        previewHtml={previewHtml}
        previewSubject={previewSubject}
        diagnostics={diagnostics}
      />
    </div>
  );
};

export default CampaignStudio;
