export type Trend = {
  id: string;
  title: string;
  summary: string;
  image_url?: string;
  source?: string;
  tags: string[];
  season?: string;
  popularity: number;
  style_type?: string;
  published_at?: string;
  personal_score?: number;
  match_reason?: string;
};

export type TrendsResponse = {
  season: string;
  items: Trend[];
  personalized?: boolean;
};

export function normalizeTrendsResponse(res: TrendsResponse | Trend[]): TrendsResponse {
  if (Array.isArray(res)) {
    return { season: '', items: res };
  }
  return {
    season: res?.season ?? '',
    items: Array.isArray(res?.items) ? res.items : [],
    personalized: Boolean(res?.personalized)
  };
}
