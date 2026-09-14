/**
 * Best-effort parse of a JSON document that is still being written.
 *
 * The model streams one JSON object token by token, so at any moment the text is
 * valid JSON with some brackets and maybe one string left open. Closing them
 * speculatively yields a usable snapshot of what has arrived so far. Anything it
 * cannot make sense of returns null — a dropped frame, not an error, since the
 * next delta arrives milliseconds later.
 *
 * This only ever feeds the live preview. The authoritative object is the one the
 * `done` event carries, which the server has already validated.
 */
export function parsePartialJson<T = Record<string, unknown>>(text: string): T | null {
  const trimmed = text.trim();
  if (!trimmed) return null;

  try {
    return JSON.parse(trimmed) as T;
  } catch {
    // fall through to repair
  }

  const stack: string[] = [];
  let inString = false;
  let escaped = false;

  for (const char of trimmed) {
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\' && inString) {
      escaped = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;

    if (char === '{' || char === '[') stack.push(char);
    else if (char === '}' || char === ']') stack.pop();
  }

  let repaired = trimmed;
  // A trailing escape would re-open the string we are about to close.
  if (escaped) repaired = repaired.slice(0, -1);
  if (inString) repaired += '"';

  // Drop a dangling `,` or `:` that has no value yet.
  repaired = repaired.replace(/[,:]\s*$/, '');

  for (let i = stack.length - 1; i >= 0; i -= 1) {
    repaired += stack[i] === '{' ? '}' : ']';
  }

  try {
    return JSON.parse(repaired) as T;
  } catch {
    // fall through to the trim-back attempt
  }

  // A key whose value has not started yet (`…,"skills"`) closes into invalid
  // JSON. Drop back to the last complete entry and close from there.
  const cut = repaired.lastIndexOf(',');
  if (cut > 0) {
    let tail = trimmed.slice(0, cut);
    // Re-derive the closers for the shortened text.
    const reopened: string[] = [];
    let str = false;
    let esc = false;
    for (const char of tail) {
      if (esc) {
        esc = false;
        continue;
      }
      if (char === '\\' && str) {
        esc = true;
        continue;
      }
      if (char === '"') {
        str = !str;
        continue;
      }
      if (str) continue;
      if (char === '{' || char === '[') reopened.push(char);
      else if (char === '}' || char === ']') reopened.pop();
    }
    if (str) tail += '"';
    for (let i = reopened.length - 1; i >= 0; i -= 1) {
      tail += reopened[i] === '{' ? '}' : ']';
    }
    try {
      return JSON.parse(tail) as T;
    } catch {
      return null;
    }
  }

  return null;
}
