import React, { useState } from "react";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  Zap,
  Database,
  Calendar,
  Mail,
  Server,
  Globe,
  ExternalLink,
  Loader2,
  ChevronRight,
  ShieldCheck,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";

const STATUS_ICONS = {
  healthy: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  degraded: <AlertTriangle className="w-4 h-4 text-amber-400" />,
  error: <XCircle className="w-4 h-4 text-rose-400" />,
  not_configured: <HelpCircle className="w-4 h-4 text-fog" />,
  monitoring_unavailable: <Clock className="w-4 h-4 text-fog/60" />,
  unknown: <HelpCircle className="w-4 h-4 text-fog" />,
};

const STATUS_BADGES = {
  healthy: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  degraded: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  error: "bg-rose-500/15 text-rose-400 border-rose-500/25",
  not_configured: "bg-white/5 text-fog border-white/10",
  monitoring_unavailable: "bg-white/5 text-fog/60 border-white/10",
  unknown: "bg-white/5 text-fog border-white/10",
};

const PROVIDER_ICONS = {
  "cal.com": Calendar,
  resend: Mail,
  mongodb: Database,
  railway: Server,
  vercel: Globe,
};

export const SystemHealthTab = ({
  healthData,
  loading,
  onRefresh,
}) => {
  const { toast } = useToast();
  const [testingProvider, setTestingProvider] = useState(null);
  const [expandedProvider, setExpandedProvider] = useState(null);

  const handleTestDatabase = async () => {
    setTestingProvider("mongodb");
    try {
      const resp = await api.post("/admin/system/health/database/test");
      if (resp.data.success) {
        toast({
          title: "Database Responsive",
          description: `MongoDB Atlas ping successful (${resp.data.latency_ms}ms).`,
        });
      } else {
        toast({
          variant: "destructive",
          title: "Database Ping Failed",
          description: resp.data.message,
        });
      }
      onRefresh();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Test Error",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const handleTestCal = async () => {
    setTestingProvider("cal.com");
    try {
      const resp = await api.post("/admin/system/health/cal/test");
      if (resp.data.success) {
        toast({
          title: "Cal.com Connected",
          description: `Connected to API v2 (${resp.data.latency_ms}ms, ${resp.data.webhooks_count} webhooks active).`,
        });
      } else {
        toast({
          variant: "destructive",
          title: "Cal.com Check Failed",
          description: resp.data.message,
        });
      }
      onRefresh();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Connection Failed",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const handleTestCalWebhook = async () => {
    setTestingProvider("cal.com-webhook");
    try {
      const resp = await api.post("/admin/system/health/cal/test-webhook");
      if (resp.data.success) {
        toast({
          title: "Webhook Verified",
          description: resp.data.message,
        });
      } else {
        toast({
          variant: "destructive",
          title: "Webhook Test Failed",
          description: resp.data.message,
        });
      }
      onRefresh();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Test Error",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const handleTestResend = async () => {
    setTestingProvider("resend");
    try {
      const resp = await api.post("/admin/system/health/resend/test");
      if (resp.data.success) {
        toast({
          title: "Resend Connected",
          description: resp.data.message,
        });
      } else {
        toast({
          variant: "destructive",
          title: "Resend Test Failed",
          description: resp.data.message,
        });
      }
      onRefresh();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Test Error",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const overallStatus = healthData?.overall_status || "unknown";
  const overallBadge = STATUS_BADGES[overallStatus] || STATUS_BADGES.unknown;

  return (
    <div className="space-y-8" data-testid="system-health-tab">
      {/* 1. Overall System Status Banner */}
      <div className="bg-gradient-to-r from-obsidian via-graphite/40 to-obsidian border border-white/10 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider border ${overallBadge}`}>
                {STATUS_ICONS[overallStatus]}
                {overallStatus === "healthy" ? "All Systems Operational" : `System ${overallStatus}`}
              </span>
              <span className="text-xs text-fog font-mono">v{healthData?.version || "2.2.0"}</span>
            </div>
            <h2 className="text-xl font-display font-light text-cloud pt-2">
              Platform Health & Telemetry
            </h2>
            <p className="text-xs text-fog">
              Continuous diagnostic evaluation across database, scheduling, communications, and runtime infrastructure.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              onClick={onRefresh}
              disabled={loading}
              variant="outline"
              size="sm"
              className="border-white/10 text-ash hover:text-cloud hover:bg-white/5 rounded-lg text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
              Re-check Health
            </Button>
          </div>
        </div>
      </div>

      {/* 2. Active Incidents Callout (If any) */}
      {healthData?.recent_incidents && healthData.recent_incidents.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Active Service Warnings ({healthData.recent_incidents.length})
          </h3>
          <div className="grid grid-cols-1 gap-3">
            {healthData.recent_incidents.map((inc, i) => (
              <div
                key={i}
                className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 space-y-2 text-sm"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium text-amber-300 flex items-center gap-2">
                    <span>{inc.display_name}</span>
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-amber-500/20">
                      {inc.status}
                    </span>
                  </p>
                  <span className="text-xs text-fog font-mono">
                    {inc.occurred_at ? new Date(inc.occurred_at).toLocaleTimeString() : ""}
                  </span>
                </div>
                {inc.error && (
                  <p className="text-xs text-cloud/80 font-mono bg-black/30 p-2 rounded border border-white/5">
                    {inc.error}
                  </p>
                )}
                {inc.recommended_action && (
                  <p className="text-xs text-amber-200/90">
                    <strong className="text-amber-200">Recommended Action:</strong> {inc.recommended_action}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Integrations Health Grid with Progressive Disclosure */}
      <div className="space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-fog">
          Integration Telemetry & Subsystems
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {healthData?.integrations?.map((item) => {
            const Icon = PROVIDER_ICONS[item.provider] || Server;
            const badgeClass = STATUS_BADGES[item.status] || STATUS_BADGES.unknown;
            const isExpanded = expandedProvider === item.provider;
            const isTesting = testingProvider === item.provider;

            return (
              <div
                key={item.provider}
                className={`bg-obsidian border rounded-xl p-4 transition-all duration-200 ${
                  isExpanded ? "border-iris/40 shadow-lg" : "border-white/10 hover:border-white/20"
                }`}
                data-testid={`health-card-${item.provider}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-cloud">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-cloud">{item.display_name}</h4>
                      <p className="text-[11px] text-fog font-mono uppercase tracking-wider">{item.category}</p>
                    </div>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${badgeClass}`}>
                    {STATUS_ICONS[item.status]}
                    {item.status.replace("_", " ")}
                  </span>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 space-y-1.5 text-xs text-ash">
                  <div className="flex items-center justify-between">
                    <span className="text-fog">Connectivity</span>
                    <span className="font-mono text-cloud">{item.connectivity}</span>
                  </div>
                  {item.latency_ms !== null && item.latency_ms !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-fog">Latency</span>
                      <span className="font-mono text-emerald-400">{item.latency_ms}ms</span>
                    </div>
                  )}
                  {item.last_success_at && (
                    <div className="flex items-center justify-between">
                      <span className="text-fog">Last verified</span>
                      <span className="font-mono text-fog text-[11px]">
                        {new Date(item.last_success_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  )}
                </div>

                {/* Action Toolbar */}
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between gap-2">
                  <button
                    onClick={() => setExpandedProvider(isExpanded ? null : item.provider)}
                    className="text-[11px] text-iris hover:underline inline-flex items-center gap-0.5"
                  >
                    {isExpanded ? "Hide Details" : "View Diagnostics"}
                    <ChevronRight className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                  </button>

                  {item.provider === "mongodb" && (
                    <Button
                      onClick={handleTestDatabase}
                      disabled={isTesting}
                      variant="outline"
                      size="sm"
                      className="h-7 text-[11px] px-2 border-white/10 hover:bg-white/5 rounded-md"
                    >
                      {isTesting ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Zap className="w-3 h-3 mr-1 text-iris" />}
                      Ping DB
                    </Button>
                  )}

                  {item.provider === "cal.com" && (
                    <div className="flex items-center gap-1.5">
                      <Button
                        onClick={handleTestCal}
                        disabled={testingProvider === "cal.com"}
                        variant="outline"
                        size="sm"
                        className="h-7 text-[11px] px-2 border-white/10 hover:bg-white/5 rounded-md"
                      >
                        {testingProvider === "cal.com" ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Zap className="w-3 h-3 mr-1 text-iris" />}
                        API
                      </Button>
                      <Button
                        onClick={handleTestCalWebhook}
                        disabled={testingProvider === "cal.com-webhook"}
                        variant="outline"
                        size="sm"
                        className="h-7 text-[11px] px-2 border-white/10 hover:bg-white/5 rounded-md"
                      >
                        {testingProvider === "cal.com-webhook" ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-400" />}
                        Webhook
                      </Button>
                    </div>
                  )}

                  {item.provider === "resend" && (
                    <Button
                      onClick={handleTestResend}
                      disabled={testingProvider === "resend"}
                      variant="outline"
                      size="sm"
                      className="h-7 text-[11px] px-2 border-white/10 hover:bg-white/5 rounded-md"
                    >
                      {testingProvider === "resend" ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Zap className="w-3 h-3 mr-1 text-iris" />}
                      Test API
                    </Button>
                  )}
                </div>

                {/* Expanded Diagnostics Drawer */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-white/10 space-y-2 text-xs bg-black/20 p-3 rounded-lg">
                    {item.recommended_action && (
                      <div>
                        <p className="text-[11px] font-semibold text-amber-300">Action Required:</p>
                        <p className="text-ash text-[11px]">{item.recommended_action}</p>
                      </div>
                    )}
                    {item.affected_capabilities?.length > 0 && (
                      <div>
                        <p className="text-[11px] font-semibold text-fog">Affected Capabilities:</p>
                        <ul className="list-disc list-inside text-[11px] text-fog space-y-0.5">
                          {item.affected_capabilities.map((cap, idx) => (
                            <li key={idx}>{cap}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {item.metadata && Object.keys(item.metadata).length > 0 && (
                      <div>
                        <p className="text-[11px] font-semibold text-fog">Diagnostic Metadata:</p>
                        <pre className="text-[10px] font-mono text-ash bg-black/40 p-2 rounded overflow-x-auto">
                          {JSON.stringify(item.metadata, null, 2)}
                        </pre>
                      </div>
                    )}
                    {item.documentation_url && (
                      <a
                        href={item.documentation_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-iris hover:underline inline-flex items-center gap-1 pt-1"
                      >
                        Official Documentation <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Real-time Audit & Webhook Event Feed */}
      <div className="space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-fog flex items-center justify-between">
          <span>Recent Integration Audit Feed</span>
          <span className="text-[11px] text-fog/60 font-sans font-normal">Last 10 platform events</span>
        </h3>
        <div className="bg-obsidian border border-white/10 rounded-xl overflow-hidden shadow-md">
          {healthData?.recent_events?.length === 0 ? (
            <div className="p-8 text-center text-fog text-xs">
              No recent webhook or integration events recorded.
            </div>
          ) : (
            <div className="divide-y divide-white/5">
              {healthData?.recent_events?.map((ev) => (
                <div key={ev.id} className="p-3.5 flex items-center justify-between gap-3 text-xs hover:bg-white/[0.02]">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${
                      ev.status === "processed" ? "bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-rose-400"
                    }`} />
                    <span className="font-mono text-cloud font-medium uppercase text-[11px] shrink-0">
                      {ev.provider}
                    </span>
                    <span className="text-ash truncate">
                      {ev.event_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 font-mono text-fog text-[11px]">
                    <span>{ev.status}</span>
                    <span>{ev.received_at ? new Date(ev.received_at).toLocaleTimeString() : ""}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SystemHealthTab;
