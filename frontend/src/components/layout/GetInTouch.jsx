import React, { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CONTACT_EMAIL } from "@/data/siteData";
import BookCallModal from "@/components/shared/BookCallModal";

const GetInTouch = () => {
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);

  return (
    <section id="contact" className="bg-abyss border-t border-white/10">
      <div className="max-w-content mx-auto px-6 py-24 md:py-32 text-center">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-4xl sm:text-5xl lg:text-6xl font-display font-light text-cloud leading-[0.95] text-balance"
        >
          Have a project in mind?
          <br />
          Let's build it.
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
          className="mt-6 text-base md:text-lg font-light text-ash max-w-xl mx-auto leading-relaxed"
        >
          Book a free 30-minute call. No pitch decks, no fluff — just a
          conversation about what you're trying to build and whether we're
          the right fit.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
          className="mt-10"
        >
          <Button
            onClick={() => setIsBookModalOpen(true)}
            data-testid="get-in-touch-cta-button"
            className="bg-pure text-void hover:bg-cloud rounded-lg px-6 h-12 text-sm font-medium"
          >
            Book a Free Call
            <ArrowRight className="w-4 h-4 ml-1.5" />
          </Button>
          <p className="mt-5 text-sm text-fog">
            Or email us at{" "}
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              data-testid="get-in-touch-email-link"
              className="text-ash hover:text-cloud underline underline-offset-4 transition-colors duration-200"
            >
              {CONTACT_EMAIL}
            </a>{" "}
            — we reply within 24 hours.
          </p>
        </motion.div>
      </div>

      <BookCallModal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
      />
    </section>
  );
};

export default GetInTouch;
