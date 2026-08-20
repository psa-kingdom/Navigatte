import React, { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  User,
  LogOut,
  Shield,
  CheckCircle2,
  ChevronDown,
} from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";

export const AdminProfileDropdown = () => {
  const { admin, logout } = useAdminAuth();
  const [isOpen, setIsOpen] = useState(false);

  // Derive initials from email
  const getInitials = (email) => {
    if (!email) return "AD";
    const parts = email.split("@")[0].split(/[\._-]/);
    if (parts.length >= 2 && parts[0] && parts[1]) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return email.slice(0, 2).toUpperCase();
  };

  const initials = getInitials(admin?.email);

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <button
          aria-label="Admin account menu"
          data-testid="admin-profile-dropdown-trigger"
          className="flex items-center gap-2.5 p-1.5 sm:px-2.5 sm:py-1.5 rounded-lg bg-white/5 border border-white/10 
                     hover:bg-white/10 hover:border-white/20 transition-all duration-150 outline-none 
                     focus:ring-1 focus:ring-iris/40 group"
        >
          {/* Avatar with gradient and status indicator */}
          <div className="relative">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-iris/30 via-periwinkle/20 to-iris/40 border border-iris/30 flex items-center justify-center text-[11px] font-mono font-medium text-cloud">
              {initials}
            </div>
            <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 border border-obsidian" />
          </div>

          <div className="hidden md:flex flex-col text-left">
            <span
              data-testid="admin-user-email"
              className="text-xs font-medium text-cloud truncate max-w-[130px]"
            >
              {admin?.email || "admin@navigatte.com"}
            </span>
            <span className="text-[10px] text-fog leading-none">Administrator</span>
          </div>

          <ChevronDown className="w-3.5 h-3.5 text-fog group-hover:text-ash transition-transform duration-150 group-data-[state=open]:rotate-180" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-56 bg-obsidian/95 backdrop-blur-md border border-white/10 rounded-xl p-1.5 shadow-2xl z-50 text-cloud"
        data-testid="admin-profile-dropdown-content"
      >
        {/* User Identity Header */}
        <DropdownMenuLabel className="p-2 font-normal">
          <div className="flex items-start gap-2.5">
            <div className="w-8 h-8 rounded-full bg-iris/20 border border-iris/30 text-iris flex items-center justify-center font-mono text-xs font-semibold flex-shrink-0 mt-0.5">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-cloud truncate">
                {admin?.email || "admin@navigatte.com"}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Shield className="w-3 h-3 text-iris flex-shrink-0" />
                <span className="text-[10px] text-fog font-medium uppercase tracking-wider">
                  Admin Platform
                </span>
              </div>
            </div>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator className="bg-white/8 my-1" />

        {/* System Status Indicator */}
        <div className="px-2 py-1.5 flex items-center justify-between text-[11px] text-fog">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Session Status
          </span>
          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-ash">
            Active
          </span>
        </div>

        <DropdownMenuSeparator className="bg-white/8 my-1" />

        {/* Logout Action */}
        <DropdownMenuItem
          onClick={logout}
          data-testid="admin-logout-button"
          className="flex items-center gap-2 px-2.5 py-2 text-xs font-medium text-rose-400 hover:text-rose-300 
                     hover:bg-rose-500/10 focus:bg-rose-500/10 rounded-lg cursor-pointer transition-colors outline-none"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Log Out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default AdminProfileDropdown;
