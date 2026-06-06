'use client';

import { useCallback } from 'react';
import { create } from 'zustand';
import { api } from '@/lib/api';
import { translate } from '@/lib/i18n';
import type { Locale } from '@/lib/i18n/types';
import { useAuth } from '@/store/auth';

const STORAGE_KEY = 'couture_locale';

interface LocaleState {
  locale: Locale;
  ready: boolean;
  init: () => void;
  setLocale: (locale: Locale, opts?: { syncUser?: boolean }) => Promise<void>;
}

function applyDocumentLocale(locale: Locale) {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
    document.documentElement.dataset.locale = locale;
  }
}

export const useLocale = create<LocaleState>((set, get) => ({
  locale: 'en',
  ready: false,

  init() {
    const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
    const locale = saved === 'vi' || saved === 'en' ? saved : 'en';
    applyDocumentLocale(locale);
    set({ locale, ready: true });
  },

  async setLocale(locale, opts = { syncUser: true }) {
    localStorage.setItem(STORAGE_KEY, locale);
    applyDocumentLocale(locale);
    set({ locale });

    if (opts.syncUser) {
      const user = useAuth.getState().user;
      if (user && user.locale !== locale) {
        try {
          await api.patch('/users/me', { locale });
          useAuth.setState({ user: { ...user, locale } });
        } catch {
          /* keep local preference */
        }
      }
    }
  },

}));

export function useTranslation() {
  const locale = useLocale((s) => s.locale);
  const setLocale = useLocale((s) => s.setLocale);
  const ready = useLocale((s) => s.ready);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => translate(locale, key, params),
    [locale]
  );

  return { locale, setLocale, t, ready };
}
