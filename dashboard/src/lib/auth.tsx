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
import {
  collection,
  query,
  where,
  getDocs,
} from "firebase/firestore";
import { getAuthInstance, getDbInstance } from "./firebase";
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

      // Look up partner document by email
      try {
        const q = query(
          collection(getDbInstance(), "partners"),
          where("email", "==", user.email)
        );
        const snapshot = await getDocs(q);

        if (snapshot.empty) {
          setState({
            user,
            partner: null,
            loading: false,
            error: "NO_PARTNER",
          });
          return;
        }

        const doc = snapshot.docs[0];
        const data = doc.data();
        const partner: Partner = {
          id: doc.id,
          email: data.email,
          displayName: data.displayName,
          apiKey: data.apiKey,
          authorizedEntityIds: data.authorizedEntityIds ?? [],
          isAdmin: data.isAdmin ?? false,
          status: data.status,
          invitedBy: data.invitedBy ?? null,
          createdAt: data.createdAt?.toDate() ?? new Date(),
          updatedAt: data.updatedAt?.toDate() ?? new Date(),
        };

        setState({ user, partner, loading: false, error: null });
      } catch (err) {
        console.error("Failed to fetch partner:", err);
        setState({ user, partner: null, loading: false, error: "FETCH_FAILED" });
      }
    });

    return unsubscribe;
  }, []);

  const refetchPartner = async () => {
    const currentUser = getAuthInstance().currentUser;
    if (!currentUser?.email) return;
    try {
      const q = query(
        collection(getDbInstance(), "partners"),
        where("email", "==", currentUser.email)
      );
      const snapshot = await getDocs(q);
      if (snapshot.empty) return;
      const doc = snapshot.docs[0];
      const data = doc.data();
      const partner: Partner = {
        id: doc.id,
        email: data.email,
        displayName: data.displayName,
        apiKey: data.apiKey,
        authorizedEntityIds: data.authorizedEntityIds ?? [],
        isAdmin: data.isAdmin ?? false,
        status: data.status,
        invitedBy: data.invitedBy ?? null,
        createdAt: data.createdAt?.toDate() ?? new Date(),
        updatedAt: data.updatedAt?.toDate() ?? new Date(),
      };
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
