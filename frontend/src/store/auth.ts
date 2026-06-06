'use client';

import { create } from 'zustand';
import { api, User } from '@/lib/api';

const USER_CACHE_KEY = 'rcm_user_cache';
let hydratePromise: Promise<void> | null = null;

function readCachedUser(): User | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(USER_CACHE_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function writeCachedUser(user: User | null) {
  if (typeof window === 'undefined') return;
  if (user) sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
  else sessionStorage.removeItem(USER_CACHE_KEY);
}

interface AuthState {
  user: User | null;
  loading: boolean;
  hydrated: boolean;
  access_token: string | null;
  refresh_token: string | null;
  hydrate: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name?: string, locale?: string) => Promise<void>;
  logout: () => Promise<void>;
  setTokens: (a: string, r: string) => void;
}

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  loading: false,
  hydrated: false,
  access_token: null,
  refresh_token: null,

  setTokens(a, r) {
    localStorage.setItem('access_token', a);
    localStorage.setItem('refresh_token', r);
    set({ access_token: a, refresh_token: r });
  },

  async hydrate() {
    if (hydratePromise) return hydratePromise;

    const access_token =
      typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const refresh_token =
      typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
    const cached = readCachedUser();
    set({ access_token, refresh_token, user: cached });

    if (!access_token) {
      set({ hydrated: true, user: null });
      return;
    }

    hydratePromise = (async () => {
      try {
        const user = await api.get<User>('/auth/me');
        set({ user });
        writeCachedUser(user);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        writeCachedUser(null);
        set({ user: null, access_token: null, refresh_token: null });
      } finally {
        set({ hydrated: true });
        hydratePromise = null;
      }
    })();
    return hydratePromise;
  },

  async login(email, password) {
    set({ loading: true });
    try {
      const tokens = await api.post<{ access_token: string; refresh_token: string }>('/auth/login', {
        email,
        password
      });
      get().setTokens(tokens.access_token, tokens.refresh_token);
      const user = await api.get<User>('/auth/me');
      writeCachedUser(user);
      set({ user, hydrated: true });
    } finally {
      set({ loading: false });
    }
  },

  async register(email, password, full_name, locale?: string) {
    set({ loading: true });
    try {
      await api.post<User>('/auth/register', {
        email,
        password,
        full_name,
        locale: locale || 'en'
      });
      await get().login(email, password);
    } finally {
      set({ loading: false });
    }
  },

  async logout() {
    const r = get().refresh_token;
    if (r) {
      try {
        await api.post('/auth/logout', { refresh_token: r });
      } catch {
        /* ignore */
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    writeCachedUser(null);
    set({ user: null, access_token: null, refresh_token: null, hydrated: true });
  }
}));
