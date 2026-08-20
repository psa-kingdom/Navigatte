import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Menu, ArrowRight, Globe, Bot, LayoutDashboard, Boxes, Network, Database } from "lucide-react";
import Logo from "./Logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetClose,
} from "@/components/ui/sheet";
import { SERVICES, NAV_LINKS, CTA_LINK } from "@/data/siteData";
import BookCallModal from "@/components/shared/BookCallModal";

const ICONS = { Globe, Bot, LayoutDashboard, Boxes, Network, Database };

const Navbar = () => {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const isLinkActive = (path) => location.pathname === path;

  const mobileContainerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
      },
    },
  };

  const mobileItemVariants = {
    hidden: { opacity: 0, x: 20 },
    show: { opacity: 1, x: 0 },
  };

  return (
    <header
      data-testid="navbar"
      className={cn(
        "fixed top-0 left-0 right-0 z-40 transition-all duration-300",
        scrolled
          ? "bg-obsidian/90 backdrop-blur-md border-b border-white/10 py-3 shadow-lg shadow-black/20"
          : "bg-transparent py-5"
      )}
    >
      <nav className="max-w-content mx-auto px-6 flex items-center justify-between">
        <Logo />

        <div className="hidden lg:flex items-center gap-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                data-testid="nav-solutions-dropdown-trigger"
                className={cn(
                  "px-3.5 py-2 rounded-lg text-sm transition-all duration-200 flex items-center gap-1.5 group outline-none",
                  location.pathname.startsWith("/services")
                    ? "text-iris font-medium"
                    : "text-ash hover:text-cloud hover:bg-white/5"
                )}
              >
                Solutions
                <ChevronDown className="w-3.5 h-3.5 transition-transform duration-200 group-data-[state=open]:rotate-180 opacity-70 group-hover:opacity-100" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              sideOffset={8}
              className="bg-obsidian/95 backdrop-blur-md border-white/10 w-64 p-1.5 shadow-2xl rounded-xl"
            >
              {SERVICES.map((s) => {
                const IconComponent = ICONS[s.icon];
                const isActive = location.pathname === `/services/${s.slug}`;
                return (
                  <DropdownMenuItem key={s.slug} asChild>
                    <Link
                      to={`/services/${s.slug}`}
                      data-testid={`nav-services-${s.slug}`}
                      className={cn(
                        "flex items-start gap-3 p-2.5 rounded-lg cursor-pointer transition-colors duration-150 outline-none",
                        isActive
                          ? "bg-white/5 text-iris"
                          : "text-ash hover:text-cloud hover:bg-white/5"
                      )}
                    >
                      <div className="p-1.5 rounded-md bg-white/5 border border-white/10 mt-0.5 shrink-0">
                        {IconComponent && <IconComponent className="w-3.5 h-3.5 text-iris" />}
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-sm font-medium leading-none text-cloud">
                          {s.tileTitle}
                        </span>
                        <span className="text-xs text-fog leading-relaxed line-clamp-1">
                          {s.heroSubheadline}
                        </span>
                      </div>
                    </Link>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>

          <Link
            to="/projects"
            data-testid="nav-link-projects"
            className={cn(
              "px-3.5 py-2 rounded-lg text-sm transition-colors duration-200 relative",
              isLinkActive("/projects")
                ? "text-iris font-medium"
                : "text-ash hover:text-cloud hover:bg-white/5"
            )}
          >
            {isLinkActive("/projects") && (
              <span className="absolute bottom-1 left-3.5 right-3.5 h-0.5 bg-iris rounded-full" />
            )}
            Projects
          </Link>

          {NAV_LINKS.map((link) => {
            const isActive = isLinkActive(link.href);
            return (
              <Link
                key={link.label}
                to={link.href}
                data-testid={`nav-link-${link.label.toLowerCase()}`}
                className={cn(
                  "px-3.5 py-2 rounded-lg text-sm transition-colors duration-200 relative",
                  isActive
                    ? "text-iris font-medium"
                    : "text-ash hover:text-cloud hover:bg-white/5"
                )}
              >
                {isActive && (
                  <span className="absolute bottom-1 left-3.5 right-3.5 h-0.5 bg-iris rounded-full" />
                )}
                {link.label}
              </Link>
            );
          })}
        </div>

        <div className="hidden lg:block">
          <Button
            onClick={() => setIsBookModalOpen(true)}
            data-testid="nav-book-call-button"
            className="bg-pure text-void hover:bg-cloud rounded-lg px-5 h-10 text-sm font-medium transition-transform duration-200 active:scale-95 flex items-center gap-1.5"
          >
            Book a Free Call
            <ArrowRight className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
          </Button>
        </div>

        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild className="lg:hidden">
            <button
              data-testid="nav-mobile-menu-toggle"
              className="p-2 text-cloud transition-transform duration-100 active:scale-90"
              aria-label="Open menu"
            >
              <Menu className="w-6 h-6" />
            </button>
          </SheetTrigger>
          <SheetContent
            side="right"
            className="bg-obsidian border-white/10 text-cloud w-full sm:max-w-sm"
          >
            <AnimatePresence>
              {open && (
                <motion.div
                  variants={mobileContainerVariants}
                  initial="hidden"
                  animate="show"
                  className="flex flex-col gap-1 mt-10"
                >
                  <motion.p
                    variants={mobileItemVariants}
                    className="font-mono-label text-[10px] text-fog px-3 mb-2"
                  >
                    Solutions
                  </motion.p>
                  {SERVICES.map((s) => {
                    const isActive = location.pathname === `/services/${s.slug}`;
                    const IconComponent = ICONS[s.icon];
                    return (
                      <motion.div key={s.slug} variants={mobileItemVariants}>
                        <SheetClose asChild>
                          <Link
                            to={`/services/${s.slug}`}
                            data-testid={`mobile-nav-services-${s.slug}`}
                            className={cn(
                              "px-3 py-3 rounded-lg text-sm flex items-center justify-between",
                              isActive
                                ? "text-iris bg-white/5 font-medium"
                                : "text-ash hover:text-cloud hover:bg-white/5"
                            )}
                          >
                            <div className="flex items-center gap-2.5">
                              {IconComponent && <IconComponent className="w-4.5 h-4.5 shrink-0 opacity-75" />}
                              <span>{s.tileTitle}</span>
                            </div>
                            {isActive && <div className="w-1.5 h-1.5 rounded-full bg-iris" />}
                          </Link>
                        </SheetClose>
                      </motion.div>
                    );
                  })}
                  <motion.div variants={mobileItemVariants} className="h-px bg-white/10 my-2" />
                  <motion.div variants={mobileItemVariants}>
                    <SheetClose asChild>
                      <Link
                        to="/projects"
                        data-testid="mobile-nav-link-projects"
                        className={cn(
                          "px-3 py-3 rounded-lg text-sm flex items-center justify-between",
                          isLinkActive("/projects")
                            ? "text-iris bg-white/5 font-medium"
                            : "text-ash hover:text-cloud hover:bg-white/5"
                        )}
                      >
                        Projects
                      </Link>
                    </SheetClose>
                  </motion.div>
                  {NAV_LINKS.map((link) => (
                    <motion.div key={link.label} variants={mobileItemVariants}>
                      <SheetClose asChild>
                        <Link
                          to={link.href}
                          data-testid={`mobile-nav-link-${link.label.toLowerCase()}`}
                          className={cn(
                            "px-3 py-3 rounded-lg text-sm flex items-center justify-between",
                            isLinkActive(link.href)
                              ? "text-iris bg-white/5 font-medium"
                              : "text-ash hover:text-cloud hover:bg-white/5"
                          )}
                        >
                          {link.label}
                        </Link>
                      </SheetClose>
                    </motion.div>
                  ))}
                  <motion.div variants={mobileItemVariants}>
                    <Button
                      onClick={() => {
                        setOpen(false);
                        setIsBookModalOpen(true);
                      }}
                      data-testid="mobile-nav-book-call-button"
                      className="mt-4 bg-pure text-void hover:bg-cloud rounded-lg h-11 text-sm font-medium w-full flex items-center justify-center gap-1.5"
                    >
                      Book a Free Call
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </SheetContent>
        </Sheet>
      </nav>

      <BookCallModal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
      />
    </header>
  );
};

export default Navbar;
