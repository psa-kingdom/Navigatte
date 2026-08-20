import React from "react";
import { Moon, Sun, Check, Sparkles, Eye, Shield } from "lucide-react";
import { useTheme, THEMES } from "@/context/ThemeContext";

export const AppearanceTab = () => {
  const { theme, setTheme, isEditorial } = useTheme();

  return (
    <div className="space-y-8" data-testid="appearance-tab">
      <div>
        <h2 className="text-xl font-display font-light text-cloud">
          Appearance & Design System
        </h2>
        <p className="text-xs text-fog mt-1">
          Select between two intentionally crafted visual aesthetics. Both themes feature semantic design tokens, high contrast, and accessibility compliance.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Theme 1: Obsidian Luxury Dark */}
        <div
          onClick={() => setTheme(THEMES.OBSIDIAN)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setTheme(THEMES.OBSIDIAN)}
          data-testid="theme-card-obsidian"
          className={`cursor-pointer rounded-2xl p-6 border transition-all duration-200 relative overflow-hidden flex flex-col justify-between ${
            theme === THEMES.OBSIDIAN
              ? "bg-[#0c0c12] border-iris shadow-[0_0_24px_rgba(99,102,241,0.2)] ring-1 ring-iris"
              : "bg-[#08080c] border-white/10 hover:border-white/20 opacity-75 hover:opacity-100"
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-iris/20 text-iris flex items-center justify-center">
                  <Moon className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-cloud">Obsidian</h3>
                  <p className="text-[11px] text-fog">Default Luxury Dark</p>
                </div>
              </div>
              {theme === THEMES.OBSIDIAN && (
                <span className="w-5 h-5 rounded-full bg-iris text-white flex items-center justify-center">
                  <Check className="w-3 h-3" />
                </span>
              )}
            </div>

            <p className="text-xs text-ash leading-relaxed">
              Deep space-black background with rich graphite card surfaces, glowing periwinkle/iris accents, and elevated luminance hierarchy.
            </p>

            {/* Preview Mini UI Swatch */}
            <div className="p-3 bg-[#12121c] rounded-xl border border-white/10 space-y-2 pointer-events-none">
              <div className="flex items-center justify-between text-[10px] text-fog">
                <span className="font-mono text-cloud">Overview</span>
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-mono">99.8% Healthy</span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-iris w-3/4 rounded-full" />
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-white/5 text-[11px] font-mono text-fog flex items-center justify-between">
            <span>Palette: #08080C / #12121C</span>
            <span className="text-iris">Primary Studio</span>
          </div>
        </div>

        {/* Theme 2: Editorial High-Contrast Light */}
        <div
          onClick={() => setTheme(THEMES.EDITORIAL)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setTheme(THEMES.EDITORIAL)}
          data-testid="theme-card-editorial"
          className={`cursor-pointer rounded-2xl p-6 border transition-all duration-200 relative overflow-hidden flex flex-col justify-between ${
            theme === THEMES.EDITORIAL
              ? "bg-[#ffffff] text-black border-indigo-600 shadow-[0_0_24px_rgba(79,70,229,0.2)] ring-1 ring-indigo-600"
              : "bg-[#f4f4f8] text-slate-800 border-black/10 hover:border-black/20 opacity-75 hover:opacity-100"
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/15 text-indigo-600 flex items-center justify-center">
                  <Sun className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-slate-900">Editorial</h3>
                  <p className="text-[11px] text-slate-500">Refined High-Contrast Light</p>
                </div>
              </div>
              {theme === THEMES.EDITORIAL && (
                <span className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center">
                  <Check className="w-3 h-3" />
                </span>
              )}
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Warm porcelain background with crisp pure-white elevated cards, deep charcoal typography, sharp editorial borders, and royal indigo accents.
            </p>

            {/* Preview Mini UI Swatch */}
            <div className="p-3 bg-[#ffffff] rounded-xl border border-slate-200 space-y-2 pointer-events-none shadow-sm">
              <div className="flex items-center justify-between text-[10px] text-slate-500">
                <span className="font-mono text-slate-900">Overview</span>
                <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-mono">99.8% Healthy</span>
              </div>
              <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-600 w-3/4 rounded-full" />
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-200 text-[11px] font-mono text-slate-500 flex items-center justify-between">
            <span>Palette: #FBFBFD / #FFFFFF</span>
            <span className="text-indigo-600 font-semibold">High Contrast</span>
          </div>
        </div>
      </div>

      {/* Accessibility & Motion Strip */}
      <div className="bg-obsidian border border-white/10 rounded-xl p-4 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-cloud">
            <Eye className="w-4 h-4 text-iris" />
          </div>
          <div>
            <p className="font-medium text-cloud">Reduced Motion & Accessibility</p>
            <p className="text-fog text-[11px]">Automatic support for CSS prefers-reduced-motion queries.</p>
          </div>
        </div>
        <span className="font-mono text-[11px] text-emerald-400 flex items-center gap-1">
          <Shield className="w-3.5 h-3.5" /> Enforced
        </span>
      </div>
    </div>
  );
};

export default AppearanceTab;
