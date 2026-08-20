import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Layers,
  Palette,
  Shield,
  RefreshCw,
  User,
  CheckCircle2,
} from "lucide-react";
import SystemHealthTab from "./SystemHealthTab";
import IntegrationsTab from "./IntegrationsTab";
import AppearanceTab from "./AppearanceTab";
import { useAdminAuth } from "@/context/AdminAuthContext";
import api from "@/lib/api";

const SUB_TABS = [
  { id: "health", label: "System Health", icon: Activity },
  { id: "integrations", label: "Integrations", icon: Layers },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "general", label: "General & Security", icon: Shield },
];

export const AdminSettingsView = () => {
  const { admin } = useAdminAuth();
  const [activeSubTab, setActiveSubTab] = useState("health");
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get("/admin/system/health");
      setHealthData(resp.data);
    } catch (err) {
      console.error("Failed to fetch system health:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return (
    <div className="space-y-8" data-testid="admin-settings-view">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-light text-cloud">
          Settings & Operational Control Centre
        </h1>
        <p className="text-sm text-fog mt-1">
          System telemetry, third-party provider bridges, dual-theme styling, and security control.
        </p>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-px overflow-x-auto">
        {SUB_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              data-testid={`settings-subtab-${tab.id}`}
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

      {/* Tab Panels */}
      <div>
        {activeSubTab === "health" && (
          <SystemHealthTab
            healthData={healthData}
            loading={loading}
            onRefresh={fetchHealth}
          />
        )}

        {activeSubTab === "integrations" && (
          <IntegrationsTab
            healthData={healthData}
            onRefresh={fetchHealth}
          />
        )}

        {activeSubTab === "appearance" && <AppearanceTab />}

        {activeSubTab === "general" && (
          <div className="space-y-6 max-w-2xl bg-obsidian border border-white/10 rounded-2xl p-6 shadow-md">
            <div>
              <h3 className="text-base font-medium text-cloud">Administrator Identity & Session</h3>
              <p className="text-xs text-fog mt-0.5">Authenticated security context and active privileges</p>
            </div>

            <div className="space-y-3 pt-3 border-t border-white/5 text-xs">
              <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                <span className="text-fog">Account Email</span>
                <span className="font-mono text-cloud">{admin?.email || "admin@navigatte.com"}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                <span className="text-fog">Assigned Role</span>
                <span className="font-mono text-iris uppercase text-[11px] font-semibold">{admin?.role || "Administrator"}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                <span className="text-fog">Session Security</span>
                <span className="font-mono text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> JWT HS256 / SameSite Protected
                </span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                <span className="text-fog">Lockout Policy</span>
                <span className="font-mono text-fog">5 Failed Attempts / 15-Minute Cooldown</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminSettingsView;
