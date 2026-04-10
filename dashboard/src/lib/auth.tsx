"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  type User,
} from "firebase/auth";
import { getAuthInstance } from "./firebase";
import { getPartnerMe } from "./api";
import type { Partner } from "@/types";

interface AuthState {
  user: User | null;
  partner: Partner | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  refetchPartner: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    partner: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(getAuthInstance(), async (user) => {
      if (!user) {
        setState({ user: null, partner: null, loading: false, error: null });
        return;
      }

      try {
        const token = await user.getIdToken(true);
        const partner = await getPartnerMe(token);
        setState({ user, partner, loading: false, error: null });
      } catch (err) {
        console.error("Failed to fetch partner:", err);
        // If 404 or no partner found, set NO_PARTNER; otherwise generic failure
        const message = err instanceof Error ? err.message : "";
        const error = message.includes("404") ? "NO_PARTNER" : "FETCH_FAILED";
        setState({ user, partner: null, loading: false, error });
      }
    });

    return unsubscribe;
  }, []);

  const refetchPartner = async () => {
    const currentUser = getAuthInstance().currentUser;
    if (!currentUser) return;
    try {
      const token = await currentUser.getIdToken(true);
      const partner = await getPartnerMe(token);
      setState({ user: currentUser, partner, loading: false, error: null });
    } catch (err) {
      console.error("Failed to refetch partner:", err);
    }
  };

  const signInWithGoogle = async () => {
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(getAuthInstance(), provider);
    } catch {
      // Popup blocked or failed — fallback to redirect
      await signInWithRedirect(getAuthInstance(), provider);
    }
  };

  const signOut = async () => {
    await firebaseSignOut(getAuthInstance());
  };

  return (
    <AuthContext.Provider value={{ ...state, signInWithGoogle, signOut, refetchPartner }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
