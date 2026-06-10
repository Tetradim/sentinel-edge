export function cn(...inputs) {
  return inputs.flatMap(classNamesFromInput).filter(Boolean).join(" ");
}

function classNamesFromInput(input) {
  if (!input) return [];
  if (typeof input === "string") return [input];
  if (Array.isArray(input)) return input.flatMap(classNamesFromInput);
  if (typeof input === "object") {
    return Object.entries(input)
      .filter(([, enabled]) => Boolean(enabled))
      .map(([className]) => className);
  }
  return [String(input)];
}
