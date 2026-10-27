import { Alert, Snackbar } from "@mui/material";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface Toast { message: string; severity: "success" | "error" | "info" }
interface ToastApi {
  success: (message: string) => void;
  info: (message: string) => void;
  error: (err: unknown) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const success = useCallback((message: string) => setToast({ message, severity: "success" }), []);
  const info = useCallback((message: string) => setToast({ message, severity: "info" }), []);
  const error = useCallback((err: unknown) => setToast({ message: err instanceof Error ? err.message : String(err), severity: "error" }), []);
  const api = useMemo(() => ({ success, info, error }), [success, info, error]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <Snackbar
        open={toast !== null}
        autoHideDuration={toast?.severity === "error" ? 8000 : 4000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        {toast ? (
          <Alert severity={toast.severity} variant="filled" onClose={() => setToast(null)} sx={{ maxWidth: 560 }}>
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("ToastProvider отсутствует");
  return ctx;
}
