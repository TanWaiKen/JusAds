import { userManager } from "./cognito";

export class ApiRequestError extends Error {
  public readonly status: number;
  public readonly code?: string;

  constructor(
    message: string,
    status: number,
    code?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

/**
 * Fetch with the current Cognito ID token. The backend verifies this token and
 * derives ownership from it; no email, username, or project id is authority.
 */
export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const user = await userManager.getUser();
  const token = user?.id_token;
  if (!token || user.expired) {
    throw new ApiRequestError("Your session has expired. Please sign in again.", 401, "AUTH_REQUIRED");
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

/** Convert the backend's stable public error envelope into clear UI copy. */
export async function toApiRequestError(response: Response, fallback: string): Promise<ApiRequestError> {
  let code: string | undefined;
  let message = fallback;
  try {
    const payload = await response.json() as { error?: { code?: string; message?: string }; detail?: string };
    code = payload.error?.code;
    message = payload.error?.message || payload.detail || fallback;
  } catch {
    // A proxy or an interrupted SSE response may not have a JSON body.
  }

  if (response.status === 401) message = "Your session has expired. Please sign in again.";
  if (response.status === 403 || response.status === 404) message = "This project or task is unavailable to your account.";
  return new ApiRequestError(message, response.status, code);
}
