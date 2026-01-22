"use client";

import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface ConfirmationDialogProps {
  isOpen: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmationDialog({
  isOpen,
  title,
  description,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  if (!mounted || !isOpen) return null;

  const content = (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div className="relative w-full max-w-xs transform overflow-hidden rounded-2xl bg-card p-6 text-left shadow-xl transition-all ring-1 ring-border/50 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex flex-col gap-2 text-center">
          <h3 className="text-lg font-bold leading-6 text-foreground">
            {title}
          </h3>
          {description && (
            <p className="text-sm text-muted-foreground">
              {description}
            </p>
          )}
        </div>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row-reverse">
          <button
            type="button"
            className={cn(
              "inline-flex w-full justify-center rounded-xl px-3 py-3 text-sm font-semibold shadow-sm ring-1 ring-inset transition-all active:scale-[0.98]",
              variant === "destructive"
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90 ring-transparent"
                : "bg-primary text-primary-foreground hover:bg-primary/90 ring-transparent"
            )}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
          <button
            type="button"
            className="inline-flex w-full justify-center rounded-xl bg-secondary px-3 py-3 text-sm font-semibold text-secondary-foreground shadow-sm ring-1 ring-inset ring-border/10 hover:bg-secondary/80 transition-all active:scale-[0.98]"
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
