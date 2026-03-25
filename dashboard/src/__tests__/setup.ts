import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Global mocks for Firebase Auth — prevents real Firebase SDK initialization in all tests.
vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: vi.fn(),
  getAuth: vi.fn(),
}));

vi.mock("@/lib/firebase", () => ({
  getAuthInstance: vi.fn(),
}));
