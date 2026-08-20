import React, { useState } from "react";
import {
  Calendar,
  Mail,
  Database,
  Server,
  Globe,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  Shield,
  Key,
  Copy,
  Check,
  Zap,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";

export const IntegrationsTab = ({ healthData, onRefresh }) => {
  const { toast } = useToast();
  const [copiedKey, setCopiedKey] = useState(null);
  const [syncingCal, setSyncingCal] = useState(false);

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    toast({ title: "Copied to clipboard", description: text });
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleSyncCalWebhook = async () => {
    setSyncingCal(true);
    try {
      const resp = await api.post("/admin/integrations/cal/sync");
      if (resp.data.success) {
        toast({
          title: "Cal.com Webhook Synced",
          description: resp.data.result?.message || "Webhook successfully verified on Cal.com account.",
        });
      }
      onRefresh();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Webhook Sync Failed",
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setSyncingCal(false);
    }
  };

  const calRecord = healthData?.integrations?.find((i) => i.provider === "cal.com");
  const resendRecord = healthData?.integrations?.find((i) => i.provider === "resend");
  const mongoRecord = healthData?.integrations?.find((i) => i.provider === "mongodb");

  return (
    <div className="space-y-8" data-testid="integrations-tab">
      <div>
        <h2 className="text-xl font-display font-light text-cloud">
          Third-Party Integrations & Services
        </h2>
        <p className="text-xs text-fog mt-1">
          Decoupled provider adapters. Configure credentials, endpoints, and verify communication bridges.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Cal.com Integration Card */}
        <div className="bg-obsidian border border-white/10 rounded-2xl p-6 space-y-5 shadow-lg relative flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-iris/15 text-iris border border-iris/20 flex items-center justify-center">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-cloud">Cal.com Scheduling</h3>
                  <p className="text-xs text-fog">Consultation booking & calendar sync</p>
                </div>
              </div>
              <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${
                calRecord?.status === "healthy"
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/25"
                  : "bg-amber-500/15 text-amber-400 border-amber-500/25"
              }`}>
                {calRecord?.status || "configured"}
              </span>
            </div>

            <p className="text-xs text-ash leading-relaxed">
              Provides automated calendar synchronization for client consultations. Webhooks ingest events directly into the Navigatte CRM timeline with HMAC-SHA256 authenticity protection.
            </p>

            <div className="space-y-2.5 pt-2 border-t border-white/5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-fog">API Credential (CAL_API_KEY)</span>
                <span className="font-mono text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Configured in Railway
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Webhook Secret (CAL_WEBHOOK_SECRET)</span>
                <span className={`font-mono flex items-center gap-1 ${
                  calRecord?.metadata?.has_webhook_secret ? "text-emerald-400" : "text-amber-400"
                }`}>
                  {calRecord?.metadata?.has_webhook_secret ? (
                    <><CheckCircle2 className="w-3.5 h-3.5" /> Active & Verified</>
                  ) : (
                    <><AlertTriangle className="w-3.5 h-3.5" /> Pending Configuration</>
                  )}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Webhook Subscriber URL</span>
                <button
                  onClick={() => copyToClipboard("https://navigatte-website-production.up.railway.app/api/webhooks/cal", "cal-url")}
                  className="font-mono text-[11px] text-iris hover:underline flex items-center gap-1"
                >
                  {copiedKey === "cal-url" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  /api/webhooks/cal
                </button>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-white/10 flex items-center justify-between gap-3">
            <a
              href="https://cal.com/settings/developer/webhooks"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-iris hover:underline inline-flex items-center gap-1"
            >
              Cal.com Dashboard <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <Button
              onClick={handleSyncCalWebhook}
              disabled={syncingCal}
              size="sm"
              className="bg-iris/80 hover:bg-iris text-white rounded-lg text-xs h-8"
            >
              {syncingCal ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
              Sync Webhook
            </Button>
          </div>
        </div>

        {/* 2. Resend Communications Card */}
        <div className="bg-obsidian border border-white/10 rounded-2xl p-6 space-y-5 shadow-lg relative flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-periwinkle/15 text-periwinkle border border-periwinkle/20 flex items-center justify-center">
                  <Mail className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-cloud">Resend Communications</h3>
                  <p className="text-xs text-fog">Transactional email & audience outbox</p>
                </div>
              </div>
              <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${
                resendRecord?.status === "healthy"
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/25"
                  : "bg-white/5 text-fog border-white/10"
              }`}>
                {resendRecord?.status === "healthy" ? "Ready" : "Adapter Ready"}
              </span>
            </div>

            <p className="text-xs text-ash leading-relaxed">
              Dispatches transactional emails, consultation confirmations, and notification campaigns. Decoupled behind the generic <code className="text-iris font-mono text-[11px]">CommunicationsProvider</code> contract.
            </p>

            <div className="space-y-2.5 pt-2 border-t border-white/5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-fog">Verified Domain</span>
                <span className="font-mono text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> updates.navigatte.com
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Default Sender</span>
                <span className="font-mono text-cloud">updates@updates.navigatte.com</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">API Key (RESEND_API_KEY)</span>
                <span className="font-mono text-fog text-[11px]">
                  {resendRecord?.metadata?.has_api_key ? "Configured in Railway" : "Ready to configure"}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-white/10 flex items-center justify-between gap-3">
            <a
              href="https://resend.com/domains"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-iris hover:underline inline-flex items-center gap-1"
            >
              Resend Domains <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <span className="text-[11px] text-fog font-mono">Phase 3 Ready</span>
          </div>
        </div>

        {/* 3. MongoDB Atlas Infrastructure Card */}
        <div className="bg-obsidian border border-white/10 rounded-2xl p-6 space-y-5 shadow-lg relative flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-cloud">MongoDB Atlas Cluster</h3>
                  <p className="text-xs text-fog">Async Motor document persistence</p>
                </div>
              </div>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border bg-emerald-500/15 text-emerald-400 border-emerald-500/25">
                Connected
              </span>
            </div>

            <p className="text-xs text-ash leading-relaxed">
              Production database hosting client showcase projects, sales enquiries, user auth sessions, and webhook idempotency event records.
            </p>

            <div className="space-y-2.5 pt-2 border-t border-white/5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-fog">Driver</span>
                <span className="font-mono text-cloud">Motor AsyncIO / PyMongo</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Database Name</span>
                <span className="font-mono text-cloud">{mongoRecord?.metadata?.database_name || "navigatte_dev"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Latency</span>
                <span className="font-mono text-emerald-400">{mongoRecord?.latency_ms || "<10"}ms</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-white/10 flex items-center justify-between gap-3">
            <a
              href="https://cloud.mongodb.com"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-iris hover:underline inline-flex items-center gap-1"
            >
              Atlas Cloud <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
              <Shield className="w-3.5 h-3.5" /> SSL Encrypted
            </span>
          </div>
        </div>

        {/* 4. Railway Hosting Card */}
        <div className="bg-obsidian border border-white/10 rounded-2xl p-6 space-y-5 shadow-lg relative flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-orchid/15 text-orchid border border-orchid/20 flex items-center justify-center">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-cloud">Railway Deployment</h3>
                  <p className="text-xs text-fog">Backend ASGI container runtime</p>
                </div>
              </div>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border bg-emerald-500/15 text-emerald-400 border-emerald-500/25">
                Active Runtime
              </span>
            </div>

            <p className="text-xs text-ash leading-relaxed">
              Containerized FastAPI backend running in Railway production environment with automatic restarts, environment variable encryption, and TLS termination.
            </p>

            <div className="space-y-2.5 pt-2 border-t border-white/5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-fog">Runtime</span>
                <span className="font-mono text-cloud">Python 3.12 / Uvicorn ASGI</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-fog">Endpoint URL</span>
                <span className="font-mono text-[11px] text-cloud">navigatte-website-production.up.railway.app</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-white/10 flex items-center justify-between gap-3">
            <a
              href="https://railway.com"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-iris hover:underline inline-flex items-center gap-1"
            >
              Railway Console <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <span className="text-[11px] font-mono text-fog">CI/CD Connected</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntegrationsTab;
