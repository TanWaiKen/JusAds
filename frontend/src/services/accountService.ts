import { API_BASE } from "@/lib/apiConfig";
import { authenticatedFetch, toApiRequestError } from "@/lib/apiAuth";
import type { BusinessProfile, ZernioConnection } from "@/models/account";

export async function getBusinessProfile(): Promise<BusinessProfile | null> {
  const response = await authenticatedFetch(`${API_BASE}/api/account/profile`);
  if (response.status === 404) return null;
  if (!response.ok) throw await toApiRequestError(response, "Business profile could not be loaded.");
  return response.json() as Promise<BusinessProfile>;
}

export async function saveBusinessProfile(profile: BusinessProfile): Promise<BusinessProfile> {
  const response = await authenticatedFetch(`${API_BASE}/api/account/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!response.ok) throw await toApiRequestError(response, "Business profile could not be saved.");
  return response.json() as Promise<BusinessProfile>;
}

export async function getOnboardingStatus(): Promise<{ onboarding_complete: boolean }> {
  const response = await authenticatedFetch(`${API_BASE}/api/account/onboarding-status`);
  if (!response.ok) throw await toApiRequestError(response, "Onboarding status could not be loaded.");
  return response.json() as Promise<{ onboarding_complete: boolean }>;
}

export async function getZernioConnection(): Promise<ZernioConnection> {
  const response = await authenticatedFetch(`${API_BASE}/api/user/zernio/connection`);
  if (!response.ok) throw await toApiRequestError(response, "Zernio connection could not be loaded.");
  return response.json() as Promise<ZernioConnection>;
}

export async function saveZernioConnection(apiKey: string): Promise<ZernioConnection> {
  const response = await authenticatedFetch(`${API_BASE}/api/user/zernio/connection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Zernio API key could not be saved.");
  return response.json() as Promise<ZernioConnection>;
}

export async function disconnectZernioConnection(): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/user/zernio/connection`, { method: "DELETE" });
  if (!response.ok) throw await toApiRequestError(response, "Zernio connection could not be removed.");
}
