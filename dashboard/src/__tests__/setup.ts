import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Global mocks for Firebase — prevents real Firebase SDK initialization in all tests.
// Both alias (@/lib/firebase) and relative (../lib/firebase, ./firebase) paths are
// covered by mocking the actual module path.
vi.mock("firebase/firestore", () => ({
  collection: vi.fn(),
  query: vi.fn(),
  where: vi.fn(),
  getDocs: vi.fn(),
  doc: vi.fn(),
  getDoc: vi.fn(),
}));

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: vi.fn(),
  getAuth: vi.fn(),
}));

vi.mock("@/lib/firebase", () => ({
  getDbInstance: vi.fn(),
  getAuthInstance: vi.fn(),
}));
