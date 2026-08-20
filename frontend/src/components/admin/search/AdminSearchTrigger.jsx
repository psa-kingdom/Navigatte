import React from "react";
import { Search } from "lucide-react";

export const AdminSearchTrigger = ({ onClick }) => {
  return (
    <>
      {/* Desktop Trigger */}
      <button
        onClick={onClick}
        aria-label="Search navigation, leads, and projects"
        data-testid="admin-search-trigger-desktop"
        className="hidden sm:flex items-center justify-between gap-3 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 
                   text-fog hover:text-cloud hover:bg-white/10 hover:border-white/20 transition-all duration-150 text-xs 
                   w-48 md:w-64 outline-none focus:ring-1 focus:ring-iris/40 group"
      >
        <span className="flex items-center gap-2 truncate">
          <Search className="w-3.5 h-3.5 text-fog group-hover:text-iris transition-colors shrink-0" />
          <span className="truncate">Search commands, leads...</span>
        </span>
        <kbd className="inline-flex items-center gap-0.5 text-[10px] font-mono text-fog bg-white/5 border border-white/10 px-1.5 py-0.5 rounded group-hover:border-white/20 shrink-0">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>

      {/* Mobile Trigger */}
      <button
        onClick={onClick}
        aria-label="Search navigation, leads, and projects"
        data-testid="admin-search-trigger-mobile"
        className="flex sm:hidden items-center justify-center w-8 h-8 rounded-lg bg-white/5 border border-white/10 
                   text-fog hover:text-cloud hover:bg-white/10 transition-colors outline-none"
      >
        <Search className="w-4 h-4" />
      </button>
    </>
  );
};

export default AdminSearchTrigger;
