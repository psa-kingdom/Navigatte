import React, { useState, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import {
  X, Mail, Phone, Copy, Check, Building2, MessageSquare,
  Clock, ChevronDown, Plus, Loader2, Tag, Calendar,
  ExternalLink, Video, CheckCircle2, AlertCircle, RefreshCw,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import api from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

// Status pipeline configuration
const STATUS_CONFIG = {
  new: { label: "New", color: "bg-iris/15 text-iris border-iris/25" },
  contacted: { label: "Contacted", color: "bg-signal/15 text-signal border-signal/25" },
  qualified: { label: "Qualified", color: "bg-periwinkle/15 text-periwinkle border-periwinkle/25" },
  converted: { label: "Converted", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" },
  closed: { label: "Closed", color: "bg-white/5 text-ash border-white/10" },
};

const SCHEDULING_STATUS_CONFIG = {
  booked: { label: "Call Booked", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30", icon: Calendar },
  rescheduled: { label: "Rescheduled", color: "bg-signal/15 text-signal border-signal/30", icon: RefreshCw },
  cancelled: { label: "Cancelled", color: "bg-rose-500/15 text-rose-400 border-rose-500/30", icon: XCircle },
  completed: { label: "Completed", color: "bg-iris/15 text-iris border-iris/30", icon: CheckCircle2 },
  no_show: { label: "No Show", color: "bg-white/5 text-fog border-white/10", icon: AlertCircle },
};

const PIPELINE_ORDER = ["new", "contacted", "qualified", "converted", "closed"];

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric",
  });
}

function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function CopyButton({ value, label }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard fallback
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 text-sm text-ash hover:text-cloud transition-colors 
                 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-1.5 
                 font-mono tabular-nums truncate max-w-full group"
      title={`Copy ${label}`}
    >
      <span className="truncate">{value}</span>
      {copied
        ? <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
        : <Copy className="w-3.5 h-3.5 flex-shrink-0 opacity-60 group-hover:opacity-100" />}
    </button>
  );
}

function StatusDropdown({ lead, onStatusChanged }) {
  const [open, setOpen] = useState(false);
  const [updating, setUpdating] = useState(false);
  const { toast } = useToast();
  const current = STATUS_CONFIG[lead.status] ?? STATUS_CONFIG.new;

  const handleSelect = async (status) => {
    if (status === lead.status) {
      setOpen(false);
      return;
    }
    setUpdating(true);
    setOpen(false);
    try {
      await api.patch(`/admin/enquiries/${lead.id}/status`, { status });
      onStatusChanged({ ...lead, status });
      toast({ title: `Status updated to ${STATUS_CONFIG[status]?.label ?? status}` });
    } catch {
      toast({ title: "Failed to update status", variant: "destructive" });
    } finally {
      setUpdating(false);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          disabled={updating}
          className={`flex items-center gap-2 border rounded-lg px-3 py-1.5 text-xs font-medium 
                      transition-colors ${current.color} hover:opacity-90 outline-none focus:ring-1 focus:ring-iris/40`}
          data-testid="lead-status-dropdown-trigger"
        >
          {updating ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
          {current.label}
          <ChevronDown className="w-3 h-3 opacity-60" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        sideOffset={6}
        className="bg-graphite border border-white/10 rounded-lg p-1.5 shadow-2xl min-w-[150px] z-[60]"
      >
        {PIPELINE_ORDER.map((s) => {
          const cfg = STATUS_CONFIG[s];
          const isCurrent = s === lead.status;
          return (
            <DropdownMenuItem
              key={s}
              onClick={() => handleSelect(s)}
              className={`flex items-center justify-between px-2.5 py-1.5 text-xs font-medium rounded-md cursor-pointer
                          hover:bg-white/10 focus:bg-white/10 outline-none transition-colors ${
                            isCurrent ? "bg-white/5" : ""
                          }`}
            >
              <span
                className={`inline-flex items-center gap-1.5 border rounded px-2 py-0.5 ${cfg.color}`}
              >
                {cfg.label}
              </span>
              {isCurrent && <Check className="w-3.5 h-3.5 text-iris ml-2" />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function NoteComposer({ lead, onNoteAdded }) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      const resp = await api.post(`/admin/enquiries/${lead.id}/notes`, { text: text.trim() });
      onNoteAdded(resp.data);
      setText("");
      toast({ title: "Note added" });
    } catch {
      toast({ title: "Failed to add note", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Add an internal note…"
        rows={3}
        className="bg-obsidian border-white/10 text-cloud text-sm resize-none 
                   placeholder:text-fog focus:border-iris/40"
      />
      <Button
        type="submit"
        disabled={saving || !text.trim()}
        size="sm"
        className="bg-iris/80 hover:bg-iris text-white rounded-lg"
      >
        {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Plus className="w-3.5 h-3.5 mr-1.5" />}
        Add Note
      </Button>
    </form>
  );
}

// Main LeadDrawer component with Portal mounting and Activity Timeline
const LeadDrawer = ({ lead: initialLead, onClose, onLeadUpdated }) => {
  const [lead, setLead] = useState(initialLead);

  const handleStatusChanged = useCallback((updated) => {
    setLead(updated);
    onLeadUpdated?.(updated);
  }, [onLeadUpdated]);

  const handleNoteAdded = useCallback((updated) => {
    setLead(updated);
    onLeadUpdated?.(updated);
  }, [onLeadUpdated]);

  const booking = lead?.booking;
  const schedulingCfg = SCHEDULING_STATUS_CONFIG[lead?.scheduling_status || booking?.status] || null;

  // Combine internal notes and activities into a unified chronological feed
  const timelineItems = useMemo(() => {
    const items = [];

    if (lead?.notes) {
      lead.notes.forEach((n) => {
        items.push({
          id: `note-${n.id}`,
          kind: "note",
          date: new Date(n.created_at),
          title: n.created_by,
          text: n.text,
          raw: n,
        });
      });
    }

    if (lead?.activities) {
      lead.activities.forEach((a) => {
        items.push({
          id: `activity-${a.id}`,
          kind: "activity",
          date: new Date(a.timestamp),
          title: a.title,
          summary: a.summary,
          type: a.type,
          source: a.source,
          raw: a,
        });
      });
    }

    return items.sort((a, b) => b.date - a.date);
  }, [lead?.notes, lead?.activities]);

  if (!lead) return null;

  const drawerContent = (
    <div className="fixed inset-0 z-50 pointer-events-none">
      {/* Full-viewport Backdrop */}
      <motion.div
        key="lead-drawer-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm pointer-events-auto"
        onClick={onClose}
        aria-hidden="true"
        data-testid="lead-drawer-backdrop"
      />

      {/* Full-height Drawer Panel */}
      <motion.div
        key="lead-drawer-panel"
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 26, stiffness: 280 }}
        className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-obsidian border-l border-white/10 
                   flex flex-col overflow-hidden shadow-2xl pointer-events-auto"
        role="dialog"
        aria-modal="true"
        aria-label={`Lead details for ${lead.name}`}
        data-testid="lead-drawer"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-6 border-b border-white/10 flex-shrink-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-display font-light text-cloud truncate" data-testid="lead-drawer-name">
                {lead.name}
              </h2>
              {lead.is_test && (
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25">
                  Test Lead
                </span>
              )}
            </div>
            {lead.company && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <Building2 className="w-3 h-3 text-fog flex-shrink-0" />
                <span className="text-sm text-ash truncate">{lead.company}</span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg 
                       text-fog hover:text-cloud hover:bg-white/5 transition-colors"
            aria-label="Close lead details"
            data-testid="lead-drawer-close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Status + submitted */}
          <div className="flex items-center justify-between">
            <StatusDropdown lead={lead} onStatusChanged={handleStatusChanged} />
            <div className="flex items-center gap-1.5 text-xs text-fog">
              <Clock className="w-3 h-3" />
              {formatDate(lead.created_at)}
            </div>
          </div>

          {/* Scheduled Booking Card (if present) */}
          {booking && (
            <div className="p-4 rounded-lg bg-graphite/40 border border-white/10 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-semibold text-cloud">Scheduled Consultation</span>
                </div>
                {schedulingCfg && (
                  <span className={`text-[10px] font-medium border rounded px-2 py-0.5 ${schedulingCfg.color}`}>
                    {schedulingCfg.label}
                  </span>
                )}
              </div>

              <div className="space-y-1 text-xs">
                <p className="text-cloud font-medium">{booking.event_title || "Consultation Call"}</p>
                {booking.scheduled_start && (
                  <p className="text-fog">
                    {formatDateTime(booking.scheduled_start)}
                    {booking.timezone && ` (${booking.timezone})`}
                  </p>
                )}
              </div>

              {booking.meeting_url && (
                <a
                  href={booking.meeting_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-iris hover:text-iris/80 transition-colors pt-1"
                >
                  <Video className="w-3.5 h-3.5" />
                  Join Video Session
                  <ExternalLink className="w-3 h-3 ml-0.5" />
                </a>
              )}
            </div>
          )}

          {/* Contact info */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-fog uppercase tracking-wider">Contact</p>
            <div className="space-y-1.5">
              <CopyButton value={lead.email} label="email" />
              {lead.phone && <CopyButton value={lead.phone} label="phone" />}
            </div>
          </div>

          {/* Service interest */}
          {lead.service_interest && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-fog uppercase tracking-wider">Service Interest</p>
              <div className="flex items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-iris" />
                <span className="text-sm text-ash">{lead.service_interest}</span>
              </div>
            </div>
          )}

          {/* Message */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-fog uppercase tracking-wider flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" />
              Message
            </p>
            <p className="text-sm text-ash leading-relaxed whitespace-pre-wrap bg-white/3 
                         border border-white/8 rounded-lg p-3">
              {lead.message}
            </p>
          </div>

          {/* Timeline & Notes Feed */}
          <div className="space-y-3">
            <p className="text-xs font-medium text-fog uppercase tracking-wider">
              Activity Timeline & Notes {timelineItems.length > 0 && `(${timelineItems.length})`}
            </p>

            {timelineItems.length > 0 ? (
              <div className="space-y-2.5">
                {timelineItems.map((item) => (
                  <div
                    key={item.id}
                    className={`rounded-lg p-3 space-y-1.5 border ${
                      item.kind === "activity"
                        ? "bg-iris/5 border-iris/20"
                        : "bg-graphite/40 border-white/8"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-xs font-medium ${item.kind === "activity" ? "text-iris" : "text-fog"}`}>
                        {item.title}
                      </span>
                      <span className="text-[11px] text-fog font-mono">
                        {formatDateTime(item.date)}
                      </span>
                    </div>
                    <p className="text-sm text-cloud leading-relaxed">
                      {item.kind === "activity" ? item.summary : item.text}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fog italic">No activity recorded yet.</p>
            )}

            <NoteComposer lead={lead} onNoteAdded={handleNoteAdded} />
          </div>
        </div>
      </motion.div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(drawerContent, document.body);
};

export default LeadDrawer;
