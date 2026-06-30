/**
 * NotFoundPage — shown when a project/task does not exist or access is denied.
 * Handles both 404 (not found) and 403 (not your resource) cases.
 */

import { useNavigate, useLocation } from "react-router";
import { ShieldOff, FolderX } from "lucide-react";

type ErrorType = "not_found" | "unauthorized";

interface NotFoundState {
  type?: ErrorType;
  message?: string;
}

export default function NotFoundPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as NotFoundState | null;

  const type = state?.type ?? "not_found";
  const isUnauthorized = type === "unauthorized";

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-8 text-center">
      <div className={`flex h-20 w-20 items-center justify-center rounded-2xl ${isUnauthorized ? "bg-amber-500/10" : "bg-muted"}`}>
        {isUnauthorized ? (
          <ShieldOff className="h-10 w-10 text-amber-500" />
        ) : (
          <FolderX className="h-10 w-10 text-muted-foreground" />
        )}
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">
          {isUnauthorized ? "Access Denied" : "Not Found"}
        </h1>
        <p className="text-muted-foreground max-w-sm">
          {state?.message ?? (
            isUnauthorized
              ? "This project doesn't belong to your account. You don't have permission to view it."
              : "This project or task doesn't exist. It may have been deleted or the link is incorrect."
          )}
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/dashboard")}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Go to Dashboard
        </button>
        <button
          onClick={() => navigate(-1)}
          className="rounded-md border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
        >
          Go Back
        </button>
      </div>
    </div>
  );
}
