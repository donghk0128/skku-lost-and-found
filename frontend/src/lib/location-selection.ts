import type { LocationOption } from "@/lib/ai-api";

export type LocationNumberAnswer =
  | { kind: "selection"; ids: string[] }
  | { kind: "invalid" }
  | { kind: "text" };

export function parseLocationNumbers(content: string, options: LocationOption[]): LocationNumberAnswer {
  const text = content.trim().replace(/번/g, "");
  if (!text || !/^[\d\s,，、]+$/.test(text)) return { kind: "text" };
  const numbers = text.split(/[\s,，、]+/).filter(Boolean).map(Number);
  if (!numbers.length || numbers.some(number => !Number.isInteger(number) || number < 1 || number > options.length)) return { kind: "invalid" };
  return { kind: "selection", ids: [...new Set(numbers.map(number => options[number - 1].id))] };
}
