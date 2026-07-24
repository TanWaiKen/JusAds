const configuredApiBase = import.meta.env.VITE_API_BASE;
const developmentApiBase = import.meta.env.DEV ? "http://localhost:8000" : "";

/** Backend origin without a trailing slash; production defaults to same-origin. */
export const API_BASE = (configuredApiBase ?? developmentApiBase).replace(/\/+$/, "");

interface ApiErrorPayload {
  error?: string;
  message?: string;
}

/** Extract a safe backend error message, falling back to the HTTP status. */
export async function getApiError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return payload.error || payload.message || `${fallback} (${response.status})`;
  } catch {
    return `${fallback} (${response.status})`;
  }
}
