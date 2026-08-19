import React, { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Menu,
  X,
  ChevronRight,
  Sparkles,
  Lock,
  Command,
} from "lucide-react";
import {
  ADMIN_NAV_SECTIONS,
  ADMIN_NAV_ITEMS,
} from "@/config/adminNavigationConfig";
import Logo from "@/components/layout/Logo";

const drawerVariants = {
  closed: {
    x: "-100%",
    opacity: 0.8,
    transition: { type: "spring", damping: 28, stiffness: 300 },
  },
  open: {
    x: "0%",
    opacity: 1,
    transition: { type: "spring", damping: 28, stiffness: 300 },
  },
};

const backdropVariants = {
  closed: { opacity: 0, transition: { duration: 0.2 } },
  open: { opacity: 1, transition: { duration: 0.2 } },
};

export const AdminNavigationDrawer = ({
  activeTab,
  onSelectTab,
  isOpen,
  onOpenChange,
}) => {
  const closeTimeoutRef = useRef(null);
  const drawerRef = useRef(null);

  const clearCloseTimeout = useCallback(() => {
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current);
      closeTimeoutRef.current = null;
    }
  }, []);

  const scheduleClose = useCallback(() => {
    clearCloseTimeout();
    closeTimeoutRef.current = setTimeout(() => {
      onOpenChange(false);
    }, 280);
  }, [clearCloseTimeout, onOpenChange]);

  const handleMouseEnter = useCallback(() => {
    clearCloseTimeout();
  }, [clearCloseTimeout]);

  const handleMouseLeave = useCallback(() => {
    scheduleClose();
  }, [scheduleClose]);

  // Keyboard accessibility: Escape to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onOpenChange(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onOpenChange]);

  const handleItemClick = (item) => {
    if (item.status === "active") {
      onSelectTab(item.id);
      onOpenChange(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="admin-nav-backdrop"
            variants={backdropVariants}
            initial="closed"
            animate="open"
            exit="closed"
            onClick={() => onOpenChange(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            aria-hidden="true"
            data-testid="admin-nav-backdrop"
          />

          {/* Slide-out Navigation Drawer */}
          <motion.aside
            key="admin-nav-drawer"
            ref={drawerRef}
            variants={drawerVariants}
            initial="closed"
            animate="open"
            exit="closed"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            className="fixed top-0 left-0 bottom-0 w-80 max-w-[85vw] bg-obsidian/95 border-r border-white/10 
                       z-50 flex flex-col shadow-2xl backdrop-blur-xl"
            role="navigation"
            aria-label="Admin Navigation Menu"
            data-testid="admin-nav-drawer"
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 flex-shrink-0">
              <div className="flex items-center gap-3">
                <Logo />
                <span className="text-[11px] font-mono-label px-2 py-0.5 rounded bg-white/5 border border-white/10 text-fog">
                  Admin
                </span>
              </div>
              <button
                onClick={() => onOpenChange(false)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-fog hover:text-cloud hover:bg-white/5 transition-colors"
                aria-label="Close navigation"
                data-testid="admin-nav-close-button"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Navigation Body */}
            <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
              {ADMIN_NAV_SECTIONS.map((section) => (
                <div key={section.category} className="space-y-1.5">
                  <h3 className="px-3 text-[10px] font-mono-label uppercase tracking-widest text-fog/70 font-semibold">
                    {section.category}
                  </h3>
                  <div className="space-y-1">
                    {section.items.map((item) => {
                      const Icon = item.icon;
                      const isActive = activeTab === item.id;
                      const isAvailable = item.status === "active";

                      return (
                        <button
                          key={item.id}
                          onClick={() => handleItemClick(item)}
                          disabled={!isAvailable}
                          data-testid={`admin-nav-item-${item.id}`}
                          className={`w-full group text-left px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all duration-150 relative
                            ${
                              isActive
                                ? "bg-iris/15 text-cloud border border-iris/25 font-medium shadow-sm"
                                : isAvailable
                                ? "text-ash hover:text-cloud hover:bg-white/5 border border-transparent"
                                : "text-fog/50 cursor-not-allowed opacity-60 border border-transparent"
                            }`}
                        >
                          {/* Active accent pill */}
                          {isActive && (
                            <span className="absolute left-0 top-2 bottom-2 w-1 bg-iris rounded-r-full" />
                          )}

                          <div
                            className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 transition-colors
                              ${
                                isActive
                                  ? "bg-iris/20 text-iris"
                                  : isAvailable
                                  ? "bg-white/5 text-ash group-hover:text-cloud group-hover:bg-white/10"
                                  : "bg-white/2 text-fog/40"
                              }`}
                          >
                            <Icon className="w-4 h-4" strokeWidth={1.8} />
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1">
                              <span className="text-xs font-medium truncate">
                                {item.label}
                              </span>
                              {item.badge && (
                                <span
                                  className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full flex-shrink-0
                                    ${
                                      isActive
                                        ? "bg-iris/30 text-iris"
                                        : isAvailable
                                        ? "bg-white/8 text-fog"
                                        : "bg-white/3 text-fog/50"
                                    }`}
                                >
                                  {item.badge}
                                </span>
                              )}
                            </div>
                            <p className="text-[10px] text-fog truncate mt-0.5">
                              {item.description}
                            </p>
                          </div>

                          {isAvailable && (
                            <ChevronRight
                              className={`w-3.5 h-3.5 text-fog flex-shrink-0 transition-transform duration-150
                                ${
                                  isActive
                                    ? "text-iris translate-x-0.5"
                                    : "opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5"
                                }`}
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-white/10 bg-white/2 flex items-center justify-between text-[11px] text-fog">
              <span className="flex items-center gap-1.5">
                <Command className="w-3.5 h-3.5 text-iris" />
                Navigatte Admin
              </span>
              <span className="font-mono">v1.2</span>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
};

export default AdminNavigationDrawer;
