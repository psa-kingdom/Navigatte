/**
 * RecipientChips — Gmail-style email chip input component.
 *
 * Allows entering multiple email addresses as visual chips via comma, Enter, Tab,
 * or semicolon as delimiters. Invalid emails are flagged in red. Duplicates are
 * rejected silently.
 *
 * Props:
 *   values: string[]        — current list of email strings
 *   onChange: fn(string[])  — called with updated list
 *   placeholder: string     — input placeholder text
 *   validate: fn(string) => boolean  — custom validator (defaults to basic email check)
 *   disabled: boolean       — disables all interaction
 *   maxChips: number        — max allowed chips (default 500)
 */
import React, { useState, useRef, useCallback } from "react";
import { X, Mail, AlertCircle } from "lucide-react";

const DEFAULT_VALIDATE = (email) => {
  if (!email || !email.trim()) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
};

const DELIMITERS = [",", ";", "\n", "\t"];

export const RecipientChips = ({
  values = [],
  onChange,
  placeholder = "Enter email addresses…",
  validate = DEFAULT_VALIDATE,
  disabled = false,
  maxChips = 500,
}) => {
  const [inputValue, setInputValue] = useState("");
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);

  const addChip = useCallback(
    (raw) => {
      const emails = raw
        .split(/[,;\n\t]+/)
        .map((e) => e.trim().toLowerCase())
        .filter((e) => e.length > 0);

      if (emails.length === 0) return;

      const existing = new Set(values.map((v) => v.toLowerCase()));
      const toAdd = emails.filter((e) => !existing.has(e));

      if (toAdd.length === 0) return;
      if (values.length >= maxChips) return;

      const newValues = [...values, ...toAdd].slice(0, maxChips);
      onChange(newValues);
    },
    [values, onChange, maxChips]
  );

  const removeChip = useCallback(
    (email) => {
      onChange(values.filter((v) => v !== email));
    },
    [values, onChange]
  );

  const handleKeyDown = (e) => {
    // Add chip on Enter, comma, semicolon, tab
    if (["Enter", ",", ";", "Tab"].includes(e.key)) {
      if (inputValue.trim()) {
        e.preventDefault();
        addChip(inputValue.trim());
        setInputValue("");
      }
      return;
    }
    // Remove last chip on Backspace if input is empty
    if (e.key === "Backspace" && !inputValue && values.length > 0) {
      removeChip(values[values.length - 1]);
    }
  };

  const handleChange = (e) => {
    const val = e.target.value;
    // Check if a delimiter was typed inline
    const lastChar = val[val.length - 1];
    if (lastChar && DELIMITERS.includes(lastChar)) {
      const toProcess = val.slice(0, -1).trim();
      if (toProcess) {
        addChip(toProcess);
      }
      setInputValue("");
    } else {
      setInputValue(val);
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text");
    if (pasted) {
      addChip(pasted);
      setInputValue("");
    }
  };

  const handleBlur = () => {
    setFocused(false);
    if (inputValue.trim()) {
      addChip(inputValue.trim());
      setInputValue("");
    }
  };

  const containerClick = () => {
    if (!disabled) inputRef.current?.focus();
  };

  const invalidChips = new Set(values.filter((v) => !validate(v)));

  return (
    <div
      onClick={containerClick}
      className={`
        min-h-[40px] w-full rounded-lg border px-2 py-1.5 flex flex-wrap gap-1.5 items-center
        cursor-text transition-all
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        ${
          focused
            ? "border-iris/60 bg-white/[0.06] ring-1 ring-iris/20"
            : "border-white/10 bg-white/[0.03] hover:border-white/20"
        }
      `}
    >
      {values.map((email) => {
        const isInvalid = invalidChips.has(email);
        return (
          <span
            key={email}
            className={`
              inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono
              border transition-colors group
              ${
                isInvalid
                  ? "bg-rose-500/20 border-rose-500/50 text-rose-300"
                  : "bg-iris/15 border-iris/30 text-iris hover:bg-iris/25"
              }
            `}
            title={isInvalid ? `Invalid email: ${email}` : email}
          >
            {isInvalid ? (
              <AlertCircle className="w-2.5 h-2.5 shrink-0" />
            ) : (
              <Mail className="w-2.5 h-2.5 shrink-0 opacity-60" />
            )}
            <span className="max-w-[200px] truncate">{email}</span>
            {!disabled && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeChip(email);
                }}
                className="ml-0.5 opacity-60 hover:opacity-100 transition-opacity rounded-full"
                aria-label={`Remove ${email}`}
              >
                <X className="w-2.5 h-2.5" />
              </button>
            )}
          </span>
        );
      })}

      {!disabled && values.length < maxChips && (
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onFocus={() => setFocused(true)}
          onBlur={handleBlur}
          placeholder={values.length === 0 ? placeholder : "Add another…"}
          className="flex-1 min-w-[140px] bg-transparent outline-none text-xs text-cloud placeholder:text-fog/50 font-mono py-0.5"
          aria-label={placeholder}
        />
      )}

      {values.length > 0 && (
        <span className="ml-auto text-[10px] text-fog font-mono shrink-0">
          {values.length}/{maxChips}
        </span>
      )}
    </div>
  );
};

export default RecipientChips;
