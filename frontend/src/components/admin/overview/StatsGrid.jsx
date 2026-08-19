import React from "react";
import { motion } from "framer-motion";
import { Inbox, TrendingUp, FolderOpen, Activity, ArrowRight } from "lucide-react";

const CARDS = [
  {
    key: "enquiries_new",
    label: "New Enquiries",
    icon: Inbox,
    accent: "iris",
    iconBg: "bg-iris/10",
    iconColor: "text-iris",
    borderAccent: "border-iris/20",
    tab: "enquiries",
    tabParam: "new",
    description: "Unread leads",
  },
  {
    key: "enquiries_pipeline",
    label: "Pipeline Active",
    icon: TrendingUp,
    accent: "signal",
    iconBg: "bg-signal/10",
    iconColor: "text-signal",
    borderAccent: "border-signal/20",
    tab: "enquiries",
    tabParam: "contacted",
    description: "Contacted & qualified",
  },
  {
    key: "projects_published",
    label: "Live Projects",
    icon: FolderOpen,
    accent: "periwinkle",
    iconBg: "bg-periwinkle/10",
    iconColor: "text-periwinkle",
    borderAccent: "border-periwinkle/20",
    tab: "projects",
    tabParam: null,
    description: "Published to portfolio",
  },
  {
    key: "projects_total",
    label: "Total Projects",
    icon: Activity,
    accent: "orchid",
    iconBg: "bg-orchid/10",
    iconColor: "text-orchid",
    borderAccent: "border-orchid/20",
    tab: "projects",
    tabParam: null,
    description: "All statuses",
  },
];

const containerVariants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.08 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

const StatsGrid = ({ stats, loading, onTabChange }) => {
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="grid grid-cols-2 lg:grid-cols-4 gap-4"
    >
      {CARDS.map((card) => {
        const Icon = card.icon;
        const value = loading ? null : (stats?.[card.key] ?? 0);

        return (
          <motion.div
            key={card.key}
            variants={cardVariants}
            className={`group relative bg-graphite/40 border ${card.borderAccent} rounded-feature p-5 
                        hover:bg-graphite/60 transition-colors duration-200 cursor-pointer`}
            onClick={() => onTabChange?.(card.tab)}
            data-testid={`stat-card-${card.key}`}
          >
            {/* Icon */}
            <div className={`inline-flex items-center justify-center w-9 h-9 rounded-lg ${card.iconBg} mb-4`}>
              <Icon className={`w-4.5 h-4.5 ${card.iconColor}`} strokeWidth={1.8} />
            </div>

            {/* Value */}
            <div className="flex items-baseline gap-1.5 mb-1">
              {loading ? (
                <div className="h-8 w-12 bg-white/5 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-display font-light text-cloud tabular-nums">
                  {value}
                </span>
              )}
            </div>

            {/* Label */}
            <p className="text-sm font-medium text-ash leading-tight">{card.label}</p>
            <p className="text-xs text-fog mt-0.5">{card.description}</p>

            {/* Hover arrow */}
            <ArrowRight
              className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-fog 
                         opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 
                         transition-all duration-200"
            />
          </motion.div>
        );
      })}
    </motion.div>
  );
};

export default StatsGrid;
