import React, { useState, useRef, useCallback } from "react";
import { Menu, LogOut, Command } from "lucide-react";
import { Button } from "@/components/ui/button";
import Logo from "@/components/layout/Logo";
import { useAdminAuth } from "@/context/AdminAuthContext";
import AdminNavigationDrawer from "@/components/admin/navigation/AdminNavigationDrawer";
import { ADMIN_NAV_ITEMS } from "@/config/adminNavigationConfig";

export const AdminShell = ({
  activeTab,
  onSelectTab,
  children,
  headerExtra = null,
}) => {
  const { admin, logout } = useAdminAuth();
  const [isNavOpen, setIsNavOpen] = useState(false);
  const hoverTimeoutRef = useRef(null);

  const clearHoverTimeout = useCallback(() => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = null;
    }
  }, []);

  const handleTriggerMouseEnter = useCallback(() => {
    clearHoverTimeout();
    setIsNavOpen(true);
  }, [clearHoverTimeout]);

  const handleTriggerMouseLeave = useCallback(() => {
    clearHoverTimeout();
    // A small buffer so the user can transition pointer from trigger to drawer
    hoverTimeoutRef.current = setTimeout(() => {
      // The drawer's own mouse enter/leave will keep it open if hovered
    }, 200);
  }, [clearHoverTimeout]);

  const currentItem =
    ADMIN_NAV_ITEMS.find((item) => item.id === activeTab) ||
    ADMIN_NAV_ITEMS[0];
  const CurrentIcon = currentItem?.icon;

  return (
    <div className="min-h-screen bg-obsidian text-cloud flex flex-col">
      {/* Navigation Drawer Overlay */}
      <AdminNavigationDrawer
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        isOpen={isNavOpen}
        onOpenChange={setIsNavOpen}
      />

      {/* Top Application Header */}
      <header className="border-b border-white/10 sticky top-0 bg-obsidian/90 backdrop-blur-md z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          {/* Left: Navigation Trigger + Brand + Current Section */}
          <div className="flex items-center gap-4">
            {/* Persistent Navigation Trigger */}
            <button
              onClick={() => setIsNavOpen((prev) => !prev)}
              onMouseEnter={handleTriggerMouseEnter}
              onMouseLeave={handleTriggerMouseLeave}
              aria-label="Toggle Admin Navigation"
              aria-expanded={isNavOpen}
              data-testid="admin-nav-trigger"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 
                         text-ash hover:text-cloud hover:bg-white/10 hover:border-white/20 transition-all duration-150 group"
            >
              <Menu className="w-4 h-4 text-cloud group-hover:text-iris transition-colors" />
              <span className="text-xs font-medium hidden sm:inline">Menu</span>
            </button>

            <div className="h-5 w-px bg-white/10 hidden sm:block" />

            <Logo />

            {/* Current Active Section Badge */}
            {currentItem && (
              <div className="hidden md:flex items-center gap-2 pl-2 border-l border-white/10">
                <div className="w-5 h-5 rounded bg-iris/15 text-iris flex items-center justify-center">
                  {CurrentIcon && <CurrentIcon className="w-3 h-3" />}
                </div>
                <span className="text-xs font-medium text-ash">
                  {currentItem.label}
                </span>
                {currentItem.badge && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-fog">
                    {currentItem.badge}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Right: Extra tools / Admin Session Info & Logout */}
          <div className="flex items-center gap-3">
            {headerExtra}

            <span
              data-testid="admin-user-email"
              className="text-xs text-ash hidden lg:inline font-mono px-2.5 py-1 rounded bg-white/3 border border-white/5"
            >
              {admin?.email}
            </span>

            <Button
              onClick={logout}
              data-testid="admin-logout-button"
              variant="outline"
              size="sm"
              className="border-white/15 text-ash hover:text-cloud hover:bg-white/5 rounded-lg h-8 text-xs px-3"
            >
              <LogOut className="w-3.5 h-3.5 mr-1.5" />
              Log Out
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content Body */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        {children}
      </main>
    </div>
  );
};

export default AdminShell;
