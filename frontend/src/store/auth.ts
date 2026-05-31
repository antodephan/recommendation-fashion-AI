'use client';

import { create } from 'zustand';
import { api, User } from '@/lib/api';

interface AuthState {
  user: User | null;
  loading: boolean;
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
  access_token: typeof window !== 'undefined' ? localStorage.getItem('access_token') : null,
  refresh_token: typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null,

  setTokens(a, r) {
    localStorage.setItem('access_token', a);
    localStorage.setItem('refresh_token', r);
    set({ access_token: a, refresh_token: r });
  },

  async hydrate() {
    if (!get().access_token) return;
    try {
      const user = await api.get<User>('/auth/me');
      set({ user });
    } catch {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      set({ user: null, access_token: null, refresh_token: null });
    }
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
      set({ user });
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
    set({ user: null, access_token: null, refresh_token: null });
  }
}));
