import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

type ToastTone = 'info' | 'success' | 'warning' | 'error';

type ToastItem = {
  id: number;
  message: string;
  tone: ToastTone;
};

type ToastContextValue = {
  push: (message: string, tone?: ToastTone) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback((message: string, tone: ToastTone = 'info') => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => removeToast(id), 3500);
  }, [removeToast]);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`}>
            <span>{toast.message}</span>
            <button onClick={() => removeToast(toast.id)} aria-label="Dismiss notification">×</button>
          </div>
        ))}
      </div>
      <style jsx global>{`
        .toast-stack {
          position: fixed;
          right: 20px;
          bottom: 20px;
          z-index: 1000;
          display: grid;
          gap: 10px;
          width: min(360px, calc(100vw - 40px));
        }

        .toast {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 14px;
          border-radius: 14px;
          box-shadow: 0 16px 40px rgba(15, 23, 42, 0.10);
          background: rgba(248, 250, 252, 0.96);
          border: 1px solid rgba(15, 23, 42, 0.08);
          animation: toast-in 160ms ease-out;
        }

        .toast span {
          line-height: 1.35;
          font-size: 14px;
          color: #0f172a;
        }

        .toast button {
          border: none;
          background: transparent;
          font-size: 18px;
          line-height: 1;
          cursor: pointer;
          color: #64748b;
          margin-top: -2px;
        }

        .toast-info { border-left: 4px solid #2563eb; }
        .toast-success { border-left: 4px solid #16a34a; }
        .toast-warning { border-left: 4px solid #d97706; }
        .toast-error { border-left: 4px solid #dc2626; }

        @keyframes toast-in {
          from { transform: translateY(6px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
