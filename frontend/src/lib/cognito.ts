import { UserManager, WebStorageStateStore } from "oidc-client-ts";
import type { UserManagerSettings } from "oidc-client-ts";

// Derive the redirect URI — must exactly match what is registered
// in the Cognito App Client "Allowed callback URLs".
// Registered values should include both:
//   http://localhost:5173/callback  (dev)
//   https://yourdomain.com/callback (prod)
const redirectUri = `${window.location.origin}/callback`;

const cognitoAuthConfig: UserManagerSettings = {
  authority:
    "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_8hAosB1se",
  client_id: "41rfef3ni43sfr2v9lnjk0prj5",
  redirect_uri: redirectUri,
  post_logout_redirect_uri: window.location.origin,
  response_type: "code",
  scope: "email openid profile",
  automaticSilentRenew: true,
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  // Disable silent renew iframe — Cognito does not support it without
  // a dedicated silent-renew page; it causes 400s on the token endpoint.
  silent_redirect_uri: undefined,
  monitorSession: false,
};

// create a UserManager instance
export const userManager = new UserManager(cognitoAuthConfig);

export async function signOutRedirect(): Promise<void> {
  const clientId = "41rfef3ni43sfr2v9lnjk0prj5";
  const logoutUri = encodeURIComponent(window.location.origin);
  const cognitoDomain =
    "https://ap-southeast-18haosb1se.auth.ap-southeast-1.amazoncognito.com";
  window.location.href = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${logoutUri}`;
}


