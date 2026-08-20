import React, { useState, useRef, useCallback } from "react";
import { Menu } from "lucide-react";
import Logo from "@/components/layout/Logo";
import { useAdminAuth } from "@/context/AdminAuthContext";
import AdminNavigationDrawer from "@/components/admin/navigation/AdminNavigationDrawer";
import AdminProfileDropdown from "@/components/admin/layout/AdminProfileDropdown";
import AdminSearchTrigger from "@/components/admin/search/AdminSearchTrigger";
import GlobalAdminSearch from "@/components/admin/search/GlobalAdminSearch";
import { ADMIN_NAV_ITEMS } from "@/config/adminNavigationConfig";

export const AdminShell = ({
  activeTab,
  onSelectTab,
  children,
  headerExtra = null,
  onAction = null,
}) => {
  const { admin } = useAdminAuth();
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
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
    // Buffer for smooth pointer transition to drawer
    hoverTimeoutRef.current = setTimeout(() => {
      // The drawer will maintain open state if hovered
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

      {/* Global Command & Search Dialog */}
      <GlobalAdminSearch
        isOpen={isSearchOpen}
        onOpenChange={setIsSearchOpen}
        onSelectTab={onSelectTab}
        onAction={onAction}
      />

      {/* Top Application Header */}
      <header className="border-b border-white/10 sticky top-0 bg-obsidian/90 backdrop-blur-md z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3 sm:gap-4">
          {/* Left: Navigation Trigger + Brand + Current Section */}
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            {/* Persistent Navigation Trigger */}
            <button
              onClick={() => setIsNavOpen((prev) => !prev)}
              onMouseEnter={handleTriggerMouseEnter}
              onMouseLeave={handleTriggerMouseLeave}
              aria-label="Toggle Admin Navigation"
              aria-expanded={isNavOpen}
              data-testid="admin-nav-trigger"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 
                         text-ash hover:text-cloud hover:bg-white/10 hover:border-white/20 transition-all duration-150 group shrink-0"
            >
              <Menu className="w-4 h-4 text-cloud group-hover:text-iris transition-colors" />
              <span className="text-xs font-medium hidden sm:inline">Menu</span>
            </button>

            <div className="h-5 w-px bg-white/10 hidden sm:block shrink-0" />

            <div className="shrink-0">
              <Logo />
            </div>

            {/* Current Active Section Badge */}
            {currentItem && (
              <div className="hidden lg:flex items-center gap-2 pl-2 border-l border-white/10 truncate">
                <div className="w-5 h-5 rounded bg-iris/15 text-iris flex items-center justify-center shrink-0">
                  {CurrentIcon && <CurrentIcon className="w-3 h-3" />}
                </div>
                <span className="text-xs font-medium text-ash truncate">
                  {currentItem.label}
                </span>
                {currentItem.badge && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-fog shrink-0">
                    {currentItem.badge}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Right: Global Search Trigger + Extra tools + Admin Profile */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* Global Search Bar Trigger */}
            <AdminSearchTrigger onClick={() => setIsSearchOpen(true)} />

            {headerExtra}

            {/* Admin Profile Dropdown */}
            <AdminProfileDropdown />
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
