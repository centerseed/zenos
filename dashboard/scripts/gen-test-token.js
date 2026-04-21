#!/usr/bin/env node
/**
 * 產生 Firebase Custom Token 供 QA E2E 測試使用
 * Usage: node scripts/gen-test-token.js
 * Output: custom token (stdout)
 */
const fs = require("fs");
const { initializeApp, cert, applicationDefault, getApps } = require("firebase-admin/app");
const { getAuth } = require("firebase-admin/auth");
const path = require("path");

const TEST_UID = "I9OVKDtIQPZIv7S6YtwlN1YG6xH3";
const DEFAULT_SERVICE_ACCOUNT_ID = "firebase-adminsdk-fbsvc@zenos-naruvia.iam.gserviceaccount.com";

function resolveCredentialOptions() {
  const explicitPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  const bundledPath = path.join(__dirname, "qa-service-account.json");
  const jsonPath = explicitPath || bundledPath;

  if (jsonPath && fs.existsSync(jsonPath)) {
    const serviceAccount = require(jsonPath);
    return { credential: cert(serviceAccount) };
  }

  return {
    credential: applicationDefault(),
    serviceAccountId:
      process.env.FIREBASE_AUTH_SIGNER_SERVICE_ACCOUNT ||
      process.env.PLAYWRIGHT_SERVICE_ACCOUNT_EMAIL ||
      DEFAULT_SERVICE_ACCOUNT_ID,
  };
}

if (getApps().length === 0) {
  initializeApp(resolveCredentialOptions());
}

getAuth()
  .createCustomToken(TEST_UID)
  .then((token) => {
    process.stdout.write(token);
  })
  .catch((err) => {
    console.error("Failed to create custom token:", err.message);
    process.exit(1);
  });
