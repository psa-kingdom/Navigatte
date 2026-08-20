import React, { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Calendar, ArrowRight, CheckCircle2, Loader2,
  Sparkles, Building2, Mail, User, MessageSquare, ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { CTA_LINK } from "@/data/siteData";
import api from "@/lib/api";

const SERVICES_OPTIONS = [
  "AI & Automation Platforms",
  "Enterprise Web & Mobile",
  "Cloud Architecture & APIs",
  "Product Engineering",
  "Technology Advisory & Audit",
];

export const BookCallModal = ({ isOpen, onClose, defaultService = "" }) => {
  const [step, setStep] = useState("qualify"); // 'qualify' | 'calendar'
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
    service_interest: defaultService,
    message: "",
    hp_field: "", // Honeypot
  });
  const [errors, setErrors] = useState({});
  const [leadCreated, setLeadCreated] = useState(false);

  useEffect(() => {
    if (defaultService) {
      setFormData((prev) => ({ ...prev, service_interest: defaultService }));
    }
  }, [defaultService]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
      // Reset state on close
      setTimeout(() => {
        setStep("qualify");
        setErrors({});
        setLeadCreated(false);
      }, 300);
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const validate = () => {
    const newErrors = {};
    if (!formData.name.trim()) newErrors.name = "Full name is required";
    if (!formData.email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      newErrors.email = "Please enter a valid email address";
    }
    if (!formData.message.trim()) {
      newErrors.message = "Please share a brief note about what you are building";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmitQualification = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    try {
      // Ingest enquiry into Navigatte CRM
      await api.post("/enquiries", {
        name: formData.name.trim(),
        email: formData.email.trim(),
        company: formData.company.trim() || undefined,
        service_interest: formData.service_interest || undefined,
        message: formData.message.trim(),
        hp_field: formData.hp_field,
      });
      setLeadCreated(true);
    } catch (err) {
      // If network fails, still allow user to transition to calendar
      console.warn("Enquiry pre-submission non-blocking fallback:", err);
    } finally {
      setSubmitting(false);
      setStep("calendar");
    }
  };

  // Build prefilled Cal.com link
  const getPrefilledCalLink = useCallback(() => {
    const base = CTA_LINK.split("?")[0];
    const params = new URLSearchParams();
    if (formData.name) params.append("name", formData.name);
    if (formData.email) params.append("email", formData.email);
    if (formData.message) params.append("notes", formData.message);
    if (formData.company) params.append("company", formData.company);
    return `${base}?${params.toString()}`;
  }, [formData]);

  if (!isOpen) return null;

  const modalContent = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        onClick={onClose}
        className="fixed inset-0 bg-void/80 backdrop-blur-md"
        aria-hidden="true"
        data-testid="book-call-modal-backdrop"
      />

      {/* Modal Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="relative w-full max-w-xl bg-obsidian border border-white/10 rounded-2xl shadow-2xl overflow-hidden z-10 flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="book-call-title"
        data-testid="book-call-modal"
      >
        {/* Header */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between gap-4 flex-shrink-0 bg-graphite/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-iris/15 text-iris border border-iris/25 flex items-center justify-center">
              <Calendar className="w-4 h-4" />
            </div>
            <div>
              <h2 id="book-call-title" className="text-base font-display font-medium text-cloud">
                {step === "qualify" ? "Book a Strategy Consultation" : "Select Your Time"}
              </h2>
              <p className="text-xs text-fog">
                {step === "qualify" ? "Step 1 of 2 · 30-min discovery call" : "Step 2 of 2 · Direct calendar reservation"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close consultation modal"
            data-testid="book-call-modal-close"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-fog hover:text-cloud hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="p-6 overflow-y-auto flex-1">
          <AnimatePresence mode="wait">
            {step === "qualify" ? (
              <motion.form
                key="step-qualify"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.2 }}
                onSubmit={handleSubmitQualification}
                className="space-y-4"
                data-testid="book-call-qualification-form"
              >
                {/* Honeypot field (hidden from users) */}
                <input
                  type="text"
                  name="hp_field"
                  value={formData.hp_field}
                  onChange={(e) => setFormData({ ...formData, hp_field: e.target.value })}
                  style={{ display: "none" }}
                  tabIndex={-1}
                  autoComplete="off"
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Name */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-ash flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-fog" />
                      Your Name <span className="text-iris">*</span>
                    </label>
                    <Input
                      value={formData.name}
                      onChange={(e) => {
                        setFormData({ ...formData, name: e.target.value });
                        if (errors.name) setErrors({ ...errors, name: undefined });
                      }}
                      placeholder="Jane Doe"
                      data-testid="book-call-input-name"
                      className={`bg-graphite/40 border-white/10 text-cloud placeholder:text-fog focus:border-iris/50 ${
                        errors.name ? "border-rose-500/50" : ""
                      }`}
                    />
                    {errors.name && <p className="text-[11px] text-rose-400">{errors.name}</p>}
                  </div>

                  {/* Email */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-ash flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5 text-fog" />
                      Work Email <span className="text-iris">*</span>
                    </label>
                    <Input
                      type="email"
                      value={formData.email}
                      onChange={(e) => {
                        setFormData({ ...formData, email: e.target.value });
                        if (errors.email) setErrors({ ...errors, email: undefined });
                      }}
                      placeholder="jane@company.com"
                      data-testid="book-call-input-email"
                      className={`bg-graphite/40 border-white/10 text-cloud placeholder:text-fog focus:border-iris/50 ${
                        errors.email ? "border-rose-500/50" : ""
                      }`}
                    />
                    {errors.email && <p className="text-[11px] text-rose-400">{errors.email}</p>}
                  </div>
                </div>

                {/* Company & Service Interest */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Company */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-ash flex items-center gap-1.5">
                      <Building2 className="w-3.5 h-3.5 text-fog" />
                      Company / Organization
                    </label>
                    <Input
                      value={formData.company}
                      onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                      placeholder="Acme Corp (Optional)"
                      data-testid="book-call-input-company"
                      className="bg-graphite/40 border-white/10 text-cloud placeholder:text-fog focus:border-iris/50"
                    />
                  </div>

                  {/* Service Interest */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-ash flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-iris" />
                      Primary Focus Area
                    </label>
                    <select
                      value={formData.service_interest}
                      onChange={(e) => setFormData({ ...formData, service_interest: e.target.value })}
                      data-testid="book-call-select-service"
                      className="w-full h-10 px-3 rounded-md bg-graphite/40 border border-white/10 text-sm text-cloud focus:border-iris/50 focus:outline-none"
                    >
                      <option value="" className="bg-obsidian text-fog">Select service area...</option>
                      {SERVICES_OPTIONS.map((svc) => (
                        <option key={svc} value={svc} className="bg-obsidian text-cloud">
                          {svc}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Message */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-ash flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-fog" />
                    What can we help you build or achieve? <span className="text-iris">*</span>
                  </label>
                  <Textarea
                    rows={3}
                    value={formData.message}
                    onChange={(e) => {
                      setFormData({ ...formData, message: e.target.value });
                      if (errors.message) setErrors({ ...errors, message: undefined });
                    }}
                    placeholder="Tell us briefly about your platform goals, current tech stack, or challenges..."
                    data-testid="book-call-textarea-message"
                    className={`bg-graphite/40 border-white/10 text-cloud placeholder:text-fog focus:border-iris/50 resize-none ${
                      errors.message ? "border-rose-500/50" : ""
                    }`}
                  />
                  {errors.message && <p className="text-[11px] text-rose-400">{errors.message}</p>}
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    disabled={submitting}
                    data-testid="book-call-submit-qualification"
                    className="w-full bg-pure text-void hover:bg-cloud h-11 rounded-lg font-medium text-sm transition-all duration-200"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Saving Details...
                      </>
                    ) : (
                      <>
                        Continue to Calendar
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    )}
                  </Button>
                </div>
              </motion.form>
            ) : (
              <motion.div
                key="step-calendar"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-5 text-center py-2"
                data-testid="book-call-calendar-step"
              >
                <div className="w-12 h-12 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-6 h-6" />
                </div>

                <div className="space-y-1.5">
                  <h3 className="text-lg font-display font-medium text-cloud">
                    Ready to schedule, {formData.name.split(" ")[0]}!
                  </h3>
                  <p className="text-xs text-ash max-w-md mx-auto leading-relaxed">
                    Your project details have been captured in our CRM. Choose a 30-minute discovery slot on our calendar below.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-graphite/40 border border-white/10 text-left space-y-2 text-xs">
                  <div className="flex justify-between text-fog">
                    <span>Prospect:</span>
                    <span className="text-cloud font-medium">{formData.name}</span>
                  </div>
                  <div className="flex justify-between text-fog">
                    <span>Work Email:</span>
                    <span className="text-cloud font-mono">{formData.email}</span>
                  </div>
                  {formData.service_interest && (
                    <div className="flex justify-between text-fog">
                      <span>Focus:</span>
                      <span className="text-iris">{formData.service_interest}</span>
                    </div>
                  )}
                </div>

                <div className="pt-2 space-y-2.5">
                  <Button
                    asChild
                    data-testid="book-call-open-calendar-button"
                    className="w-full bg-iris hover:bg-iris/90 text-white h-11 rounded-lg font-medium text-sm transition-all duration-200"
                  >
                    <a href={getPrefilledCalLink()} target="_blank" rel="noopener noreferrer">
                      Open Calendar in New Tab
                      <ExternalLink className="w-4 h-4 ml-2" />
                    </a>
                  </Button>

                  <button
                    type="button"
                    onClick={() => setStep("qualify")}
                    className="text-xs text-fog hover:text-cloud transition-colors"
                  >
                    ← Edit consultation details
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modalContent, document.body);
};

export default BookCallModal;
