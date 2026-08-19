import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Mail, Phone, Copy, Check, Building2, MessageSquare,
  Clock, ChevronDown, Plus, Loader2, Tag,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
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
      // Clipboard not available in some environments
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 text-sm text-ash hover:text-cloud transition-colors 
                 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-1.5 
                 font-mono tabular-nums truncate max-w-full"
      title={`Copy ${label}`}
    >
      <span className="truncate">{value}</span>
      {copied
        ? <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
        : <Copy className="w-3.5 h-3.5 flex-shrink-0" />}
    </button>
  );
}

function StatusDropdown({ lead, onStatusChanged }) {
  const [open, setOpen] = useState(false);
  const [updating, setUpdating] = useState(false);
  const { toast } = useToast();
  const current = STATUS_CONFIG[lead.status] ?? STATUS_CONFIG.new;

  const handleSelect = async (status) => {
    if (status === lead.status) { setOpen(false); return; }
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
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={updating}
        className={`flex items-center gap-2 border rounded-lg px-3 py-1.5 text-xs font-medium 
                    transition-colors ${current.color} hover:opacity-80`}
      >
        {updating ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
        {current.label}
        <ChevronDown className="w-3 h-3" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-1.5 z-50 bg-graphite border border-white/10 
                       rounded-lg overflow-hidden shadow-xl min-w-[140px]"
          >
            {PIPELINE_ORDER.map((s) => {
              const cfg = STATUS_CONFIG[s];
              return (
                <button
                  key={s}
                  onClick={() => handleSelect(s)}
                  className={`w-full text-left px-3 py-2 text-xs font-medium transition-colors
                              hover:bg-white/5 ${s === lead.status ? "bg-white/5" : ""}`}
                >
                  <span className={`inline-flex items-center gap-1.5 border rounded px-2 py-0.5 ${cfg.color}`}>
                    {cfg.label}
                  </span>
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
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

// Main LeadDrawer component
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

  if (!lead) return null;

  const cfg = STATUS_CONFIG[lead.status] ?? STATUS_CONFIG.new;

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 26, stiffness: 280 }}
        className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-obsidian border-l border-white/10 
                   z-50 flex flex-col overflow-hidden shadow-2xl"
        data-testid="lead-drawer"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-6 border-b border-white/10 flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-lg font-display font-light text-cloud truncate" data-testid="lead-drawer-name">
              {lead.name}
            </h2>
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

          {/* Notes */}
          <div className="space-y-3">
            <p className="text-xs font-medium text-fog uppercase tracking-wider">
              Internal Notes {lead.notes?.length > 0 && `(${lead.notes.length})`}
            </p>

            {lead.notes && lead.notes.length > 0 ? (
              <div className="space-y-2.5">
                {[...lead.notes].reverse().map((note) => (
                  <div
                    key={note.id}
                    className="bg-graphite/40 border border-white/8 rounded-lg p-3 space-y-1.5"
                  >
                    <p className="text-sm text-cloud leading-relaxed">{note.text}</p>
                    <div className="flex items-center gap-2 text-xs text-fog">
                      <span>{note.created_by}</span>
                      <span>·</span>
                      <span>{formatDateTime(note.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fog italic">No notes yet.</p>
            )}

            <NoteComposer lead={lead} onNoteAdded={handleNoteAdded} />
          </div>
        </div>
      </motion.div>
    </>
  );
};

export default LeadDrawer;
