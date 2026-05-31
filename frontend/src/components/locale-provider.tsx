'use client';

import { useEffect } from 'react';
import { useLocale } from '@/store/locale';
import { useAuth } from '@/store/auth';
import type { Locale } from '@/lib/i18n/types';

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const init = useLocale((s) => s.init);
  const setLocale = useLocale((s) => s.setLocale);
  const user = useAuth((s) => s.user);

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    if (!user?.locale) return;
    const loc = user.locale as Locale;
    if (loc === 'en' || loc === 'vi') {
      setLocale(loc, { syncUser: false });
    }
  }, [user?.locale, setLocale]);

  return <>{children}</>;
}
