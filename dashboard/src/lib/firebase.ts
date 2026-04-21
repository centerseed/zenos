import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const PRODUCTION_FIREBASE_CONFIG = {
  apiKey: "AIzaSyDjAsF7t4nR34RuouBDcMOnYi6kIjVDxRA", // pragma: allowlist secret
  authDomain: "zenos-naruvia.firebaseapp.com",
  projectId: "zenos-naruvia",
  storageBucket: "zenos-naruvia.firebasestorage.app",
  messagingSenderId: "165893875709",
  appId: "1:165893875709:web:e7f2c1836462d49a601b94",
} as const;

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || PRODUCTION_FIREBASE_CONFIG.apiKey,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || PRODUCTION_FIREBASE_CONFIG.authDomain,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || PRODUCTION_FIREBASE_CONFIG.projectId,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || PRODUCTION_FIREBASE_CONFIG.storageBucket,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || PRODUCTION_FIREBASE_CONFIG.messagingSenderId,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || PRODUCTION_FIREBASE_CONFIG.appId,
};

let _app: FirebaseApp | undefined;
let _auth: Auth | undefined;

export type FirebaseBootstrapError =
  | "FIREBASE_CONFIG_MISSING"
  | "FIREBASE_CONFIG_INVALID";

function hasRequiredFirebaseConfig(): boolean {
  return Boolean(
    firebaseConfig.apiKey &&
      firebaseConfig.authDomain &&
      firebaseConfig.projectId &&
      firebaseConfig.appId
  );
}

function mapFirebaseBootstrapError(error: unknown): FirebaseBootstrapError {
  const code =
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof (error as { code?: unknown }).code === "string"
      ? String((error as { code: string }).code)
      : "";

  if (code.includes("invalid-api-key")) {
    return "FIREBASE_CONFIG_INVALID";
  }

  return "FIREBASE_CONFIG_INVALID";
}

function getApp(): FirebaseApp {
  if (!hasRequiredFirebaseConfig()) {
    throw new Error("FIREBASE_CONFIG_MISSING");
  }
  if (!_app) {
    try {
      _app =
        getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
    } catch (error) {
      throw new Error(mapFirebaseBootstrapError(error));
    }
  }
  return _app;
}

export function getAuthInstance(): Auth {
  if (!_auth) {
    try {
      _auth = getAuth(getApp());
    } catch (error) {
      if (error instanceof Error) throw error;
      throw new Error(mapFirebaseBootstrapError(error));
    }
  }
  return _auth;
}

// Dev-only: expose signInWithCustomToken for E2E testing
if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).__signInWithCustomToken = async (token: string) => {
    const { signInWithCustomToken } = await import("firebase/auth");
    return signInWithCustomToken(getAuthInstance(), token);
  };
}
