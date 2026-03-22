/** Fake Firestore Timestamp for testing date conversion logic. */
export function fakeTimestamp(date: Date) {
  return { toDate: () => date };
}
