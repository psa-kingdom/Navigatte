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
};

export const CommunicationsCentre = () => {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [outboxItems, setOutboxItems] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  // Test Email Modal State
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [testName, setTestName] = useState("");
  const [testTemplate, setTestTemplate] = useState("enquiry_acknowledgement");
  const [sendingTest, setSendingTest] = useState(false);

  // Selected Outbox Item for detail inspection
  const [selectedOutbox, setSelectedOutbox] = useState(null);

  const fetchOverview = useCallback(async () => {
    try {
      const resp = await api.get("/admin/communications/overview");
      setOverview(resp.data);
    } catch (err) {
      console.error("Failed to load communications overview:", err);
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

  const reloadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchOverview(), fetchOutbox(), fetchTemplates()]);
    setLoading(false);
  }, [fetchOverview, fetchOutbox, fetchTemplates]);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  const handleSendTest = async (e) => {
    e.preventDefault();
    if (!testEmail) {
      toast({ variant: "destructive", title: "Missing Email", description: "Please provide a valid recipient email." });
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
          service_interest: "Cloud Infrastructure Modernization",
          company: "Acme Corp",
          start_time: "Aug 25, 2026, 2:00 PM",
          timezone: "UTC",
          meeting_url: "https://navigatte.com/meet/test",
        },
      });

      if (resp.data.success) {
        toast({
          title: "Test Email Queued",
          description: `Dispatched '${testTemplate}' to ${testEmail} (Status: ${resp.data.status}).`,
        });
        setTestModalOpen(false);
        setTestEmail("");
        reloadAll();
      } else {
        toast({
          variant: "destructive",
          title: "Dispatch Failed",
          description: resp.data.error_message || "Failed to send test email.",
        });
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

  const metrics = overview?.metrics || {};
  const provider = overview?.provider || {};

  return (
    <div className="space-y-8" data-testid="communications-centre">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-light text-cloud">
            Communications Studio
          </h1>
          <p className="text-sm text-fog mt-1">
            Transactional email engine, Resend delivery telemetry, and template library.
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
          <p className="text-[11px] text-fog font-mono">Outbox items recorded</p>
        </div>

        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Delivery Rate</span>
          <p className="text-2xl font-semibold text-emerald-400">{metrics.delivery_rate_percent || 100}%</p>
          <p className="text-[11px] text-fog font-mono">{metrics.delivered_count || 0} confirmed delivered</p>
        </div>

        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Open Rate</span>
          <p className="text-2xl font-semibold text-iris">{metrics.open_rate_percent || 0}%</p>
          <p className="text-[11px] text-fog font-mono">{metrics.opened_count || 0} tracked opens</p>
        </div>

        <div className="bg-obsidian border border-white/10 rounded-xl p-4 space-y-1">
          <span className="text-xs text-fog uppercase font-mono tracking-wider">Bounce / Failed</span>
          <p className="text-2xl font-semibold text-amber-400">{metrics.bounced_count || 0}</p>
          <p className="text-[11px] text-fog font-mono">{metrics.failed_count || 0} system failures</p>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-px">
        {[
          { id: "overview", label: "Overview & Telemetry", icon: Layers },
          { id: "outbox", label: "Email Outbox", icon: Mail },
          { id: "templates", label: "Template Library", icon: FileText },
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

      {/* Tab 1: Overview */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Provider Status Card */}
          <div className="bg-obsidian border border-white/10 rounded-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-iris/15 text-iris border border-iris/20 flex items-center justify-center">
                  <Mail className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-cloud">Resend Communications Provider</h3>
                  <p className="text-xs text-fog">Verified Domain: {provider.sending_domain}</p>
                </div>
              </div>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border bg-emerald-500/15 text-emerald-400 border-emerald-500/25">
                {provider.configured ? "Connected" : "Adapter Ready"}
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

          {/* Recent Outbox Stream */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-fog">Recent Outbound Dispatches</h3>
            <div className="bg-obsidian border border-white/10 rounded-xl overflow-hidden shadow-md">
              {outboxItems.length === 0 ? (
                <div className="p-8 text-center text-fog text-xs">
                  No outbound emails recorded in outbox yet.
                </div>
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
          {/* Filter Toolbar */}
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
              </select>
            </div>
          </div>

          {/* Outbox Table */}
          <div className="bg-obsidian border border-white/10 rounded-xl overflow-hidden shadow-md">
            {outboxItems.length === 0 ? (
              <div className="p-12 text-center text-fog text-xs">
                No matching emails found in outbox.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/10 text-fog font-mono uppercase text-[11px] bg-white/[0.02]">
                    <tr>
                      <th className="p-3">Status</th>
                      <th className="p-3">Recipient</th>
                      <th className="p-3">Subject</th>
                      <th className="p-3">Template</th>
                      <th className="p-3">Dispatched At</th>
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

      {/* Tab 3: Templates */}
      {activeTab === "templates" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {templates.map((tpl) => (
            <div key={tpl.id} className="bg-obsidian border border-white/10 rounded-xl p-5 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-sm font-medium text-cloud">{tpl.name}</h4>
                  <p className="text-[11px] font-mono text-iris">{tpl.key}</p>
                </div>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                  Active
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
            </div>
          ))}
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
              <button
                onClick={() => setTestModalOpen(false)}
                className="text-fog hover:text-cloud text-xs"
              >
                ✕
              </button>
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

              <div>
                <label className="block text-fog mb-1">Template</label>
                <select
                  value={testTemplate}
                  onChange={(e) => setTestTemplate(e.target.value)}
                  className="w-full h-9 text-xs bg-white/5 border border-white/10 text-cloud rounded-lg px-2.5 outline-none"
                >
                  <option value="enquiry_acknowledgement" className="bg-[#101018]">Enquiry Intake Acknowledgement</option>
                  <option value="consultation_booking_confirmation" className="bg-[#101018]">Consultation Booking Confirmation</option>
                  <option value="consultation_rescheduled" className="bg-[#101018]">Consultation Rescheduled Notice</option>
                  <option value="consultation_cancelled" className="bg-[#101018]">Consultation Cancellation Notice</option>
                </select>
              </div>

              <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setTestModalOpen(false)}
                  className="border-white/10 text-ash text-xs h-8"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={sendingTest}
                  size="sm"
                  className="bg-iris/80 hover:bg-iris text-white text-xs h-8"
                >
                  {sendingTest ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Send className="w-3.5 h-3.5 mr-1" />}
                  Dispatch Email
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Outbox Detail Inspection Modal */}
      {selectedOutbox && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-obsidian border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-medium text-cloud truncate">
                {selectedOutbox.subject}
              </h3>
              <button
                onClick={() => setSelectedOutbox(null)}
                className="text-fog hover:text-cloud text-xs"
              >
                ✕
              </button>
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
                  {selectedOutbox.error_message}
                </div>
              )}
            </div>

            <div className="pt-2">
              <p className="text-xs font-semibold text-fog mb-1">Rendered HTML Body:</p>
              <div
                className="p-3 bg-white/5 border border-white/10 rounded-lg max-h-48 overflow-y-auto text-xs text-cloud"
                dangerouslySetInnerHTML={{ __html: selectedOutbox.body_html }}
              />
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedOutbox(null)}
                className="border-white/10 text-ash text-xs h-8"
              >
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
