#!/usr/bin/env node
/**
 * 產生 Firebase Custom Token 供 QA E2E 測試使用
 * Usage: node scripts/gen-test-token.js
 * Output: custom token (stdout)
 */
const { initializeApp, cert, getApps } = require("firebase-admin/app");
const { getAuth } = require("firebase-admin/auth");
const path = require("path");

const TEST_UID = "I9OVKDtIQPZIv7S6YtwlN1YG6xH3";
const serviceAccount = require(path.join(__dirname, "qa-service-account.json"));

if (getApps().length === 0) {
  initializeApp({ credential: cert(serviceAccount) });
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
