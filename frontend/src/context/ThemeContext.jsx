import React, { createContext, useContext, useEffect, useState, useMemo } from "react";

const THEME_STORAGE_KEY = "navigatte_theme";
export const THEMES = {
  OBSIDIAN: "obsidian",
  EDITORIAL: "editorial",
};

const ThemeContext = createContext({
  theme: THEMES.OBSIDIAN,
  setTheme: () => {},
  toggleTheme: () => {},
  isEditorial: false,
});

export const ThemeProvider = ({ children }) => {
  const [theme, setThemeState] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === THEMES.EDITORIAL || saved === THEMES.OBSIDIAN) {
        return saved;
      }
    }
    return THEMES.OBSIDIAN;
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    if (theme === THEMES.EDITORIAL) {
      root.classList.add("theme-editorial");
      root.classList.remove("theme-obsidian");
    } else {
      root.classList.add("theme-obsidian");
      root.classList.remove("theme-editorial");
    }
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = (newTheme) => {
    if (newTheme === THEMES.EDITORIAL || newTheme === THEMES.OBSIDIAN) {
      setThemeState(newTheme);
    }
  };

  const toggleTheme = () => {
    setThemeState((prev) =>
      prev === THEMES.OBSIDIAN ? THEMES.EDITORIAL : THEMES.OBSIDIAN
    );
  };

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      isEditorial: theme === THEMES.EDITORIAL,
    }),
    [theme]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);

export default ThemeProvider;
