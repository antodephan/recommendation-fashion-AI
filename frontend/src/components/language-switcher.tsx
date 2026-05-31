'use client';

import { Languages } from 'lucide-react';
import { useTranslation } from '@/store/locale';
import type { Locale } from '@/lib/i18n/types';
import { cn } from '@/lib/utils';

type Props = {
  compact?: boolean;
  className?: string;
};

export function LanguageSwitcher({ compact, className }: Props) {
  const { locale, setLocale } = useTranslation();

  async function pick(next: Locale) {
    if (next !== locale) await setLocale(next);
  }

  if (compact) {
    return (
      <div className={cn('inline-flex rounded-md border bg-card p-0.5 text-xs font-medium', className)}>
        {(['en', 'vi'] as Locale[]).map((code) => (
          <button
            key={code}
            type="button"
            onClick={() => pick(code)}
            className={cn(
              'rounded px-2 py-1 uppercase transition-colors',
              locale === code ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground'
            )}
            aria-label={code === 'en' ? 'English' : 'Tiếng Việt'}
          >
            {code}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Languages className="h-4 w-4 text-muted-foreground" aria-hidden />
      <div className="inline-flex rounded-md border bg-card p-0.5 text-sm font-medium">
        {(['en', 'vi'] as Locale[]).map((code) => (
          <button
            key={code}
            type="button"
            onClick={() => pick(code)}
            className={cn(
              'rounded px-3 py-1.5 transition-colors',
              locale === code ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {code === 'en' ? 'English' : 'Tiếng Việt'}
          </button>
        ))}
      </div>
    </div>
  );
}
