/**
 * ProductionSafetyModal — Mandatory confirmation gate for production campaign launch.
 *
 * Requires the administrator to type the exact final recipient count as a number
 * before the "Confirm Launch" button becomes active. This prevents accidental
 * production sends while still allowing deliberate, informed launches.
 *
 * Props:
 *   open: boolean           — controls modal visibility
 *   onClose: fn()           — close callback
 *   onConfirm: fn()         — called when confirmed and loading is false
 *   loading: boolean        — disables button during launch
 *   campaign: object        — campaign data { name, subject, environment }
 *   checklist: object       — validation result { target_recipients_count, ... }
 *   previewHtml: string     — rendered HTML preview (same as outbox snapshot)
 *   previewSubject: string  — rendered subject line
 *   diagnostics: object     — { provider: { from_email } }
 */
import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Send,
  ShieldCheck,
  Users,
  XCircle,
  Eye,
  Monitor,
  Smartphone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const ProductionSafetyModal = ({
  open,
  onClose,
  onConfirm,
  loading = false,
  campaign,
  checklist,
  previewHtml = "",
  previewSubject = "",
  diagnostics = null,
}) => {
  const [confirmInput, setConfirmInput] = useState("");
  const [previewMode, setPreviewMode] = useState("desktop");

  // Reset confirmation input each time modal opens
  useEffect(() => {
    if (open) {
      setConfirmInput("");
      setPreviewMode("desktop");
    }
  }, [open]);

  if (!open) return null;

  const finalCount = checklist?.target_recipients_count ?? 0;
  const isConfirmed = confirmInput.trim() === String(finalCount);
  const fromEmail = diagnostics?.provider?.from_email || "Navigatte <updates@updates.navigatte.com>";

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && !loading && onClose()}
      aria-modal="true"
      role="dialog"
      aria-labelledby="safety-modal-title"
    >
      <div className="bg-[#0e0e1a] border border-rose-500/30 rounded-2xl w-full max-w-3xl max-h-[92vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-rose-400" />
            </div>
            <div>
              <h2 id="safety-modal-title" className="text-base font-semibold text-cloud">
                Production Launch — Final Confirmation
              </h2>
              <p className="text-[11px] text-fog mt-0.5">
                Review all details below. This action will send real emails.
              </p>
            </div>
          </div>
          {!loading && (
            <button
              onClick={onClose}
              className="text-fog hover:text-cloud transition-colors p-1"
              aria-label="Close"
            >
              <XCircle className="w-5 h-5" />
            </button>
          )}
        </div>

        <div className="p-6 space-y-6">
          {/* Campaign Summary */}
          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-4 space-y-3">
            <span className="text-[10px] font-mono uppercase tracking-widest text-fog">
              Campaign Summary
            </span>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
              <div>
                <span className="text-fog">Campaign Name</span>
                <p className="text-cloud font-medium truncate mt-0.5">{campaign?.name || "—"}</p>
              </div>
              <div>
                <span className="text-fog">Environment</span>
                <p className="text-rose-400 font-mono font-semibold uppercase mt-0.5">
                  {campaign?.environment || "production"}
                </p>
              </div>
              <div>
                <span className="text-fog">From</span>
                <p className="text-cloud font-mono text-[11px] mt-0.5 truncate">{fromEmail}</p>
              </div>
              <div>
                <span className="text-fog">Subject</span>
                <p className="text-cloud font-medium mt-0.5 truncate">{previewSubject || campaign?.subject || "—"}</p>
              </div>
            </div>
          </div>

          {/* Recipient Breakdown */}
          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Users className="w-3.5 h-3.5 text-iris" />
              <span className="text-[10px] font-mono uppercase tracking-widest text-fog">
                Recipient Verification Breakdown
              </span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-xs">
              {[
                { label: "Audience", value: checklist?.audience_count ?? 0, color: "text-cloud" },
                { label: "Manual", value: checklist?.manual_additions_count ?? 0, color: "text-cloud" },
                { label: "Duplicates", value: checklist?.duplicates_count ?? 0, color: "text-amber-400" },
                { label: "Suppressed", value: checklist?.suppressed_recipients_count ?? 0, color: "text-amber-400" },
                { label: "Excluded", value: checklist?.excluded_recipients_count ?? 0, color: "text-rose-400" },
                { label: "Invalid", value: checklist?.invalid_count ?? 0, color: "text-rose-400" },
              ].map((item) => (
                <div key={item.label} className="bg-black/40 rounded-lg p-2 text-center">
                  <div className={`text-base font-bold font-mono ${item.color}`}>{item.value}</div>
                  <div className="text-[10px] text-fog mt-0.5">{item.label}</div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between px-1 pt-1 border-t border-white/10">
              <span className="text-xs text-fog">Net deliverable recipients:</span>
              <span className="text-2xl font-bold text-emerald-400 font-mono">{finalCount}</span>
            </div>
          </div>

          {/* Email Preview */}
          {previewHtml && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-[10px] font-mono uppercase tracking-widest text-fog">
                    Email Preview — Exact content recipients will receive
                  </span>
                </div>
                <div className="flex items-center gap-1 bg-white/5 p-0.5 rounded border border-white/10">
                  <button
                    onClick={() => setPreviewMode("desktop")}
                    className={`px-2 py-1 rounded text-[10px] flex items-center gap-1 transition-all ${
                      previewMode === "desktop" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                    }`}
                  >
                    <Monitor className="w-2.5 h-2.5" /> Desktop
                  </button>
                  <button
                    onClick={() => setPreviewMode("mobile")}
                    className={`px-2 py-1 rounded text-[10px] flex items-center gap-1 transition-all ${
                      previewMode === "mobile" ? "bg-iris text-white" : "text-fog hover:text-cloud"
                    }`}
                  >
                    <Smartphone className="w-2.5 h-2.5" /> Mobile
                  </button>
                </div>
              </div>

              {/* Subject preview */}
              <div className="bg-black/40 border border-white/10 rounded-lg px-3 py-2">
                <span className="text-[10px] text-fog font-mono">SUBJECT: </span>
                <span className="text-xs text-cloud">{previewSubject || campaign?.subject}</span>
              </div>

              <div className={`border border-white/10 rounded-xl overflow-hidden bg-white mx-auto shadow-lg transition-all ${
                previewMode === "mobile" ? "max-w-[400px]" : "w-full"
              }`}>
                <iframe
                  srcDoc={previewHtml}
                  title="Campaign email preview"
                  sandbox="allow-same-origin"
                  className="w-full border-0"
                  style={{ height: "320px" }}
                />
              </div>
            </div>
          )}

          {/* Safety Gate */}
          <div className="bg-rose-950/30 border border-rose-500/40 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-rose-400">
              <ShieldCheck className="w-4 h-4" />
              <span className="text-xs font-semibold uppercase tracking-wider">
                Safety Confirmation Required
              </span>
            </div>
            <p className="text-xs text-fog leading-relaxed">
              To confirm this production launch, type the exact number of final recipients
              in the field below. This prevents accidental sends.
            </p>
            <div className="flex items-center gap-3">
              <span className="text-xs text-fog whitespace-nowrap">Type recipient count:</span>
              <Input
                id="safety-count-input"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder={String(finalCount)}
                disabled={loading}
                className={`w-32 text-center font-mono text-sm font-bold h-9 transition-all ${
                  confirmInput
                    ? isConfirmed
                      ? "border-emerald-500/60 bg-emerald-950/20 text-emerald-400"
                      : "border-rose-500/60 bg-rose-950/20 text-rose-400"
                    : "border-white/20 bg-white/5 text-cloud"
                }`}
                autoFocus
              />
              {confirmInput && (
                isConfirmed
                  ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  : <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
              )}
            </div>
            {confirmInput && !isConfirmed && (
              <p className="text-[11px] text-rose-400 font-mono">
                Expected: {finalCount} — You entered: {confirmInput}
              </p>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-white/10 bg-black/20 rounded-b-2xl">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={loading}
            className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 h-9 text-xs rounded-lg"
          >
            Cancel — Do Not Send
          </Button>
          <Button
            id="confirm-launch-btn"
            onClick={onConfirm}
            disabled={!isConfirmed || loading}
            className={`h-9 px-6 text-xs rounded-lg font-semibold transition-all ${
              isConfirmed && !loading
                ? "bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-900/40"
                : "bg-white/5 text-fog cursor-not-allowed"
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                Launching Campaign…
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5 mr-2" />
                Confirm Launch — Send to {finalCount} Recipients
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ProductionSafetyModal;
