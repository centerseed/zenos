/**
 * This file previously tested getTasks/getTasksByEntity against Firestore SDK.
 * Those functions have been migrated to @/lib/api (REST API calls).
 * The equivalent tests now live in api.test.ts.
 *
 * Kept as an empty placeholder because the file cannot be deleted.
 */

import { describe, it } from "vitest";

describe("firestore-getTasks (deprecated)", () => {
  it("tests have moved to api.test.ts", () => {
    // No-op — see api.test.ts for getTasks / getTasksByEntity tests
  });
});
