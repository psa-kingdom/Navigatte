import React, { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import HeroBackgroundVideo from "@/components/home/HeroBackgroundVideo";
import BookCallModal from "@/components/shared/BookCallModal";
import { CTA_LINK, TRUST_STRIP_TEXT } from "@/data/siteData";

const Hero = () => {
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);

  const scrollToServices = (e) => {
    e.preventDefault();
    document.getElementById("services")?.scrollIntoView({ behavior: "smooth" });
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.12,
        delayChildren: 0.1,
      },
    },
  };

  const childVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        type: "spring",
        stiffness: 100,
        damping: 18,
      },
    },
  };

  return (
    <section id="hero" className="relative bg-obsidian overflow-hidden min-h-[calc(100vh-73px)] lg:h-[calc(100vh-73px)] flex items-center">
      <HeroBackgroundVideo />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-obsidian pointer-events-none z-[1]" />
      
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="relative z-10 max-w-content mx-auto px-6 py-10 md:py-12 text-center w-full"
      >
        <motion.p
          variants={childVariants}
          data-testid="hero-trust-strip"
          className="inline-block font-mono-label text-[11px] text-cloud/80 bg-black/30 backdrop-blur-md border border-white/10 rounded-pill px-4 py-2 mb-4"
        >
          {TRUST_STRIP_TEXT}
        </motion.p>

        <motion.h1
          variants={childVariants}
          data-testid="hero-headline"
          className="mt-4 text-4xl sm:text-5xl lg:text-5xl xl:text-6xl font-display font-light leading-[1.05] text-cloud text-balance max-w-4xl mx-auto [text-shadow:0_2px_24px_rgba(0,0,0,0.6)]"
        >
          Build Better Digital Products. <br className="hidden sm:inline" /> Automate Smarter. Grow Faster.
        </motion.h1>

        <motion.p
          variants={childVariants}
          data-testid="hero-subheadline"
          className="mt-4 text-base md:text-lg font-light text-cloud/90 max-w-2xl mx-auto leading-relaxed [text-shadow:0_2px_16px_rgba(0,0,0,0.6)]"
        >
          From enterprise software and AI automation to high-performing websites, 
          we help ambitious businesses transform ideas into scalable digital 
          solutions that drive measurable growth.
        </motion.p>

        <motion.div
          variants={childVariants}
          className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4 max-w-md mx-auto sm:max-w-none"
        >
          <Button
            onClick={() => setIsBookModalOpen(true)}
            data-testid="hero-primary-cta"
            className="bg-pure text-void hover:bg-cloud rounded-lg px-6 h-12 text-sm font-medium w-full sm:w-auto transition-transform duration-200 active:scale-95 flex items-center justify-center gap-1.5 shadow-lg"
          >
            Book a Free Call
            <ArrowRight className="w-4 h-4" />
          </Button>
          <button
            onClick={scrollToServices}
            data-testid="hero-secondary-cta"
            className="rounded-lg px-6 h-12 text-sm font-medium border border-white/30 bg-black/30 backdrop-blur-md text-cloud hover:bg-white/10 hover:border-white/50 transition-all duration-200 active:scale-95 w-full sm:w-auto shadow-lg"
          >
            See Our Services
          </button>
        </motion.div>
      </motion.div>

      <BookCallModal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
      />
    </section>
  );
};

export default Hero;
