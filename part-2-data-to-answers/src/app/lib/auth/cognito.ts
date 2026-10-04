import { AuthenticationDetails, CognitoRefreshToken, CognitoUser, CognitoUserPool, type CognitoUserSession } from "amazon-cognito-identity-js";
import { COGNITO_CLIENT_ID, COGNITO_USER_POOL_ID } from "@/lib/config";
import type { Session } from "./session";

let pool: CognitoUserPool | null = null;

function getPool(): CognitoUserPool {
  if (!COGNITO_USER_POOL_ID || !COGNITO_CLIENT_ID) {
    throw new Error("Sign-in is not configured (missing Cognito settings).");
  }
  pool ??= new CognitoUserPool({ UserPoolId: COGNITO_USER_POOL_ID, ClientId: COGNITO_CLIENT_ID });
  return pool;
}

function toSession(email: string, session: CognitoUserSession): Session {
  return {
    email,
    id_token: session.getIdToken().getJwtToken(),
    access_token: session.getAccessToken().getJwtToken(),
    refresh_token: session.getRefreshToken().getToken(),
    expires_at: session.getIdToken().getExpiration() * 1000,
  };
}

/** Secure Remote Password sign-in: the password never leaves the browser. */
export function signIn(email: string, password: string): Promise<Session> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: getPool() });
    user.authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), {
      onSuccess: (session) => resolve(toSession(email, session)),
      onFailure: (err) => reject(err),
      newPasswordRequired: () => reject(Object.assign(new Error("A new password is required for this account."), { code: "NewPasswordRequired" })),
      mfaRequired: () => reject(new Error("Multi-factor sign-in is not supported here.")),
    });
  });
}

export function refresh(email: string, refreshToken: string): Promise<Session> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: getPool() });
    user.refreshSession(new CognitoRefreshToken({ RefreshToken: refreshToken }), (err, session) => {
      if (err || !session) return reject(err ?? new Error("Refresh failed"));
      resolve(toSession(email, session));
    });
  });
}

export type AuthErrorKey = "invalid" | "newPassword" | "tooMany" | "network" | "notConfigured" | "generic";

/** Maps a Cognito failure to a message key, so the page can show it in the visitor's language. */
export function authErrorKey(err: unknown): AuthErrorKey {
  const code = (err as { code?: string; name?: string })?.code ?? (err as { name?: string })?.name;
  switch (code) {
    case "NotAuthorizedException":
    case "UserNotFoundException":
      return "invalid";
    case "NewPasswordRequired":
      return "newPassword";
    case "TooManyRequestsException":
    case "LimitExceededException":
      return "tooMany";
    case "NetworkError":
      return "network";
    default:
      return err instanceof Error && err.message.startsWith("Sign-in is not configured") ? "notConfigured" : "generic";
  }
}
