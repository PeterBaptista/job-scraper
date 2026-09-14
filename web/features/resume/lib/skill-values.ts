/**
 * A skill category's values live as one comma-separated string because that is
 * what `resume.py` renders. These helpers let the UI treat them as a list
 * without changing the stored shape.
 */

export function splitValues(raw: string): string[] {
  return raw
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
}

export function joinValues(values: string[]): string {
  return values.join(', ');
}

export function removeValue(raw: string, target: string): string {
  const lower = target.toLowerCase();
  return joinValues(splitValues(raw).filter((value) => value.toLowerCase() !== lower));
}

export function addValue(raw: string, addition: string): string {
  const values = splitValues(raw);
  const lower = addition.toLowerCase();
  if (values.some((value) => value.toLowerCase() === lower)) return joinValues(values);
  return joinValues([...values, addition]);
}

export function hasValue(raw: string, target: string): boolean {
  const lower = target.toLowerCase();
  return splitValues(raw).some((value) => value.toLowerCase() === lower);
}
