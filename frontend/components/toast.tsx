"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

export type ToastType = "error" | "success" | "info";

export interface ToastData {
  id: string;
  message: string;
  type: ToastType;
}

let toastListeners: ((toast: ToastData) => void)[] = [];

export function showToast(message: string, type: ToastType = "error") {
  const toast: ToastData = { id: crypto.randomUUID(), message, type };
  toastListeners.forEach((fn) => fn(toast));
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  useEffect(() => {
    const listener = (toast: ToastData) => {
      setToasts((prev) => [...prev, toast]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id));
      }, 5000);
    };
    toastListeners.push(listener);
    return () => {
      toastListeners = toastListeners.filter((l) => l !== listener);
    };
  }, []);

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-2xl backdrop-blur-xl animate-[fadeIn_0.2s_ease-out] max-w-md ${
            toast.type === "error"
              ? "border-red-500/40 bg-red-500/15 text-red-200"
              : toast.type === "success"
                ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200"
                : "border-indigo-500/40 bg-indigo-500/15 text-indigo-200"
          }`}
        >
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
            className="shrink-0 opacity-60 hover:opacity-100 transition"
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
