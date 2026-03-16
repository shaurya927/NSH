// Simple UUID-like ID generator fallback (no external dependency)
export function v4Fallback(): string {
  return 'xxxx-xxxx-xxxx'.replace(/x/g, () =>
    Math.floor(Math.random() * 16).toString(16)
  );
}
