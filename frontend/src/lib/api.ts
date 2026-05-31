/* Lightweight typed API client. Uses cookies for auth (HttpOnly access_token). */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';
const API_PREFIX = '/api/v1';

export class APIError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type FetchOptions = RequestInit & { token?: string | null; raw?: boolean; _retry?: boolean };

async function refreshAccessToken(): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE}${API_PREFIX}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ refresh_token: refresh })
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (!data.access_token) return false;
    localStorage.setItem('access_token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${API_PREFIX}${path}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  const token = options.token ?? (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(url, { ...options, headers, credentials: 'include' });
  } catch {
    throw new APIError(0, 'network_error', 'Cannot reach the API. Is the backend running?');
  }

  if (res.status === 401 && !options._retry && (await refreshAccessToken())) {
    return request<T>(path, { ...options, _retry: true });
  }

  if (options.raw) return res as unknown as T;
  const isJson = (res.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await res.json().catch(() => ({})) : await res.text();

  if (!res.ok) {
    const err = (data && (data as any).error) || { code: 'http_error', message: res.statusText };
    throw new APIError(res.status, err.code, err.message, err.details);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string, opts?: FetchOptions) => request<T>(path, { ...opts, method: 'GET' }),
  post: <T,>(path: string, body?: any, opts?: FetchOptions) =>
    request<T>(path, { ...opts, method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body ?? {}) }),
  patch: <T,>(path: string, body?: any, opts?: FetchOptions) =>
    request<T>(path, { ...opts, method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  delete: <T,>(path: string, opts?: FetchOptions) => request<T>(path, { ...opts, method: 'DELETE' })
};

export type Conversation = {
  id: string;
  title: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  image_url: string | null;
  tokens: number;
  extra: Record<string, any>;
  created_at: string;
};

export type Outfit = {
  id: string;
  name: string;
  description?: string;
  image_url?: string;
  style?: string;
  season?: string;
  gender?: string;
  occasion?: string;
  colors: string[];
  materials: string[];
  tags: string[];
  brand?: string;
  price?: number;
  currency: string;
  rating: number;
  popularity: number;
  items: Array<{
    id: string;
    category: string;
    name: string;
    brand?: string;
    color?: string;
    material?: string;
    price?: number;
    image_url?: string;
    product_url?: string;
  }>;
};

export type Recommendation = {
  id: string;
  query: string;
  reasoning: string;
  confidence: number;
  trend_score: number;
  items: Array<{
    outfit_id: string;
    name: string;
    image_url?: string;
    score: number;
    why: string;
    tags: string[];
  }>;
  weather: any;
  created_at: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: 'user' | 'admin' | 'superadmin';
  is_active: boolean;
  is_email_verified: boolean;
  gender: string | null;
  body_type: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  location: string | null;
  locale: string;
  preferences: Record<string, any>;
  created_at: string;
};
