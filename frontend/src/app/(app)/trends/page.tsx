'use client';

import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Sparkles, TrendingUp } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { useTranslation } from '@/store/locale';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  OutfitRecommendationCards,
  type OutfitRecPayload
} from '@/components/chat/outfit-recommendation-cards';

type Trend = {
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
};

type TrendsResponse = {
  season: string;
  items: Trend[];
};

export default function TrendsPage() {
  const { t } = useTranslation();
  const [season, setSeason] = useState<string>('');
  const [items, setItems] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [outfitsByTrend, setOutfitsByTrend] = useState<Record<string, OutfitRecPayload>>({});
  const [loadingOutfits, setLoadingOutfits] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TrendsResponse>('/trends')
      .then((res) => {
        setSeason(res.season);
        setItems(res.items);
      })
      .catch(() => toast.error(t('common.failed')))
      .finally(() => setLoading(false));
  }, [t]);

  async function toggleTrend(trend: Trend) {
    if (expandedId === trend.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(trend.id);
    if (outfitsByTrend[trend.id]) return;

    setLoadingOutfits(trend.id);
    try {
      const data = await api.get<OutfitRecPayload & { trend_id: string; title: string }>(
        `/trends/${trend.id}/outfits`
      );
      setOutfitsByTrend((prev) => ({ ...prev, [trend.id]: data }));
    } catch {
      toast.error(t('trends.outfitsFailed'));
      setExpandedId(null);
    } finally {
      setLoadingOutfits(null);
    }
  }

  return (
    <div className="container max-w-6xl py-8">
      <div className="mb-2 flex items-center gap-2">
        <TrendingUp className="h-5 w-5 text-accent" />
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('trends.title')}</h1>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-muted-foreground">{t('trends.subtitle')}</p>
      {season && (
        <Badge variant="secondary" className="mb-6 capitalize">
          {t('trends.seasonLabel')}: {season}
        </Badge>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-80" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => {
            const open = expandedId === item.id;
            return (
              <Card
                key={item.id}
                className={`overflow-hidden transition-shadow ${open ? 'ring-1 ring-accent/40' : ''}`}
              >
                {item.image_url && (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={item.image_url} alt={item.title} className="h-48 w-full object-cover" />
                )}
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold">{item.title}</h3>
                      <p className="text-xs text-muted-foreground">{item.source}</p>
                    </div>
                    <Badge variant="accent" title={t('trends.popularityHint')}>
                      {Math.round(item.popularity * 100)}%
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{item.summary}</p>
                  <div className="flex flex-wrap gap-1">
                    {item.tags?.slice(0, 5).map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <Button
                    variant={open ? 'secondary' : 'default'}
                    className="w-full gap-2"
                    onClick={() => toggleTrend(item)}
                  >
                    <Sparkles className="h-4 w-4" />
                    {open ? t('trends.hideOutfits') : t('trends.showOutfits')}
                    {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </Button>
                  {open && loadingOutfits === item.id && (
                    <div className="space-y-2 pt-2">
                      <Skeleton className="h-32" />
                      <Skeleton className="h-32" />
                    </div>
                  )}
                  {open && outfitsByTrend[item.id] && loadingOutfits !== item.id && (
                    <OutfitRecommendationCards data={outfitsByTrend[item.id]} />
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
