// ZenOS · Zen Ink — Shared form field wrapper
// Provides: label + helper text + error message structure reused by Input, Textarea, Select
"use client";

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

interface FormFieldProps {
  t: ZenInkTokens;
  label?: string;
  helperText?: string;
  error?: string;
  htmlFor?: string;
  required?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function FormField({
  t,
  label,
  helperText,
  error,
  htmlFor,
  required,
  children,
  style,
}: FormFieldProps) {
  const { c, fontBody, fontMono } = t;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, ...style }}>
      {label && (
        <label
          htmlFor={htmlFor}
          style={{
            fontFamily: fontBody,
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: "0.02em",
            color: error ? c.vermillion : c.inkMuted,
            cursor: "default",
          }}
        >
          {label}
          {required && (
            <span
              style={{ color: c.vermillion, marginLeft: 3 }}
              aria-hidden="true"
            >
              *
            </span>
          )}
        </label>
      )}
      {children}
      {(helperText || error) && (
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            letterSpacing: "0.02em",
            color: error ? c.vermillion : c.inkFaint,
          }}
          role={error ? "alert" : undefined}
        >
          {error ?? helperText}
        </span>
      )}
    </div>
  );
}
