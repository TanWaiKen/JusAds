import { UserManager, WebStorageStateStore } from "oidc-client-ts";
import type { UserManagerSettings } from "oidc-client-ts";

const developmentAuthority =
  "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_8hAosB1se";
const developmentClientId = "41rfef3ni43sfr2v9lnjk0prj5";
const developmentDomain =
  "https://ap-southeast-18haosb1se.auth.ap-southeast-1.amazoncognito.com";

const authority =
  import.meta.env.VITE_COGNITO_AUTHORITY?.trim() ||
  (import.meta.env.DEV ? developmentAuthority : "");
const clientId =
  import.meta.env.VITE_COGNITO_CLIENT_ID?.trim() ||
  (import.meta.env.DEV ? developmentClientId : "");
const cognitoDomain = (
  import.meta.env.VITE_COGNITO_DOMAIN?.trim() ||
  (import.meta.env.DEV ? developmentDomain : "")
).replace(/\/+$/, "");

if (!authority || !clientId || !cognitoDomain) {
  throw new Error(
    "Cognito configuration is incomplete. Set VITE_COGNITO_AUTHORITY, " +
      "VITE_COGNITO_CLIENT_ID, and VITE_COGNITO_DOMAIN.",
  );
}

const redirectUri = `${window.location.origin}/callback`;

const cognitoAuthConfig: UserManagerSettings = {
  authority,
  client_id: clientId,
  redirect_uri: redirectUri,
  post_logout_redirect_uri: window.location.origin,
  response_type: "code",
  scope: "email openid profile",
  automaticSilentRenew: true,
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  silent_redirect_uri: undefined,
  monitorSession: false,
};

export const userManager = new UserManager(cognitoAuthConfig);

export async function signOutRedirect(): Promise<void> {
  const logoutUri = encodeURIComponent(window.location.origin);
  window.location.href = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${logoutUri}`;
}
