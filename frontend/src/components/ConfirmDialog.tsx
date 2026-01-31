import { AlertTriangle, X } from "lucide-react";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  const variantStyles = {
    danger: {
      icon: "text-wsb-red",
      button: "bg-wsb-red hover:bg-red-600",
    },
    warning: {
      icon: "text-wsb-orange",
      button: "bg-wsb-orange hover:bg-orange-600",
    },
    info: {
      icon: "text-wsb-blue",
      button: "bg-wsb-blue hover:bg-blue-600",
    },
  };

  const styles = variantStyles[variant];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div className="relative bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 animate-slide-in">
        <div className="flex items-start gap-4 p-6">
          <div className={`p-2 rounded-full bg-gray-700 ${styles.icon}`}>
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <p className="mt-2 text-gray-400">{message}</p>
          </div>
          <button
            onClick={onCancel}
            className="text-gray-500 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-700">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-white rounded transition-colors ${styles.button}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
