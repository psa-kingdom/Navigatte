import React, { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import BookCallModal from "@/components/shared/BookCallModal";

const HERO_IMAGES = {
  "digital-platforms": "https://images.unsplash.com/photo-1531403009284-440f080d1e12?auto=format&fit=crop&w=1000&q=80",
  "enterprise-applications": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1000&q=80",
  "ai-automation": "https://images.unsplash.com/photo-1677442136019-21780efad99a?auto=format&fit=crop&w=1000&q=80",
  "cloud-engineering": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1000&q=80",
  "enterprise-transformation": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1000&q=80",
  "data-intelligence": "https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?auto=format&fit=crop&w=1000&q=80",
};

const ACCENT_GLOWS = {
  iris: "bg-iris/10",
  periwinkle: "bg-periwinkle/10",
  orchid: "bg-orchid/10",
  deepIris: "bg-iris-deep/10",
  paleIris: "bg-iris-pale/10",
};

const ServiceHero = ({ service }) => {
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);
  const heroImg = HERO_IMAGES[service.slug] || HERO_IMAGES["digital-platforms"];
  const accentGlow = ACCENT_GLOWS[service.accent] || ACCENT_GLOWS.iris;

  const textContainerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.1,
      },
    },
  };

  const textItemVariants = {
    hidden: { opacity: 0, x: -20 },
    visible: {
      opacity: 1,
      x: 0,
      transition: {
        type: "spring",
        stiffness: 100,
        damping: 18,
      },
    },
  };

  return (
    <section className="relative bg-obsidian overflow-hidden py-20 md:py-28 lg:py-32">
      <div className="absolute inset-0 bg-gradient-to-b from-iris/[0.06] via-transparent to-transparent pointer-events-none" />
      
      <div className="relative max-w-content mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-center">
        {/* Left Side: Content Column */}
        <motion.div
          variants={textContainerVariants}
          initial="hidden"
          animate="visible"
          className="lg:col-span-7 flex flex-col items-start text-left"
        >
          <motion.span
            variants={textItemVariants}
            data-testid="service-hero-eyebrow"
            className="inline-block font-mono-label text-[10px] text-ash bg-white/[0.06] border border-white/10 rounded-pill px-4 py-1.5 mb-6"
          >
            {service.eyebrow}
          </motion.span>

          <motion.h1
            variants={textItemVariants}
            data-testid="service-hero-headline"
            className="text-4xl sm:text-5xl lg:text-6xl font-display font-light leading-[1.05] text-cloud text-balance"
          >
            {service.heroHeadline}
          </motion.h1>

          <motion.p
            variants={textItemVariants}
            data-testid="service-hero-subheadline"
            className="mt-6 text-base md:text-lg font-light text-ash leading-relaxed max-w-2xl"
          >
            {service.heroSubhead}
          </motion.p>

          <motion.div
            variants={textItemVariants}
            className="mt-8 flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto"
          >
            <Button
              onClick={() => setIsBookModalOpen(true)}
              data-testid="service-hero-cta-button"
              className="bg-pure text-void hover:bg-cloud rounded-lg px-6 h-12 text-sm font-medium transition-transform duration-200 active:scale-95 flex items-center justify-center gap-1.5 w-full sm:w-auto"
            >
              Book a Call
              <ArrowRight className="w-4 h-4" />
            </Button>
          </motion.div>
        </motion.div>

        {/* Right Side: Image Column */}
        <div className="lg:col-span-5 relative w-full flex justify-center">
          {/* Subtle Accent Glow Source */}
          <div className={`absolute -inset-4 rounded-3xl blur-2xl opacity-40 pointer-events-none -z-10 ${accentGlow}`} />

          <motion.div
            data-testid="service-hero-visual-placeholder"
            initial={{ opacity: 0, x: 24, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 90, damping: 16, delay: 0.3 }}
            className="relative rounded-feature overflow-hidden border border-white/10 w-full aspect-[4/3] sm:aspect-[16/10] lg:aspect-[4/3] bg-graphite/10 shadow-2xl"
          >
            <img
              src={heroImg}
              alt={service.tileTitle}
              className="w-full h-full object-cover object-center transition-transform duration-700 hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent pointer-events-none" />
          </motion.div>
        </div>
      </div>

      <BookCallModal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
        defaultService={service.tileTitle}
      />
    </section>
  );
};

export default ServiceHero;
