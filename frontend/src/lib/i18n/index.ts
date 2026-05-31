import { en } from './en';
import { vi } from './vi';
import type { Locale } from './types';

const dictionaries = { en, vi } as const;

type Dict = typeof en;

function getNested(obj: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object' && key in (acc as object)) {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

export function translate(
  locale: Locale,
  key: string,
  params?: Record<string, string | number>
): string {
  const dict = dictionaries[locale] as unknown as Record<string, unknown>;
  const fallback = dictionaries.en as unknown as Record<string, unknown>;
  let value = getNested(dict, key) ?? getNested(fallback, key);
  if (typeof value !== 'string') return key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      value = (value as string).replaceAll(`{{${k}}}`, String(v));
    }
  }
  return value as string;
}

export function getDictionary(locale: Locale): Dict {
  return dictionaries[locale];
}

export { en, vi };
