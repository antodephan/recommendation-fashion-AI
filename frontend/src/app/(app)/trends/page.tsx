'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, TrendingUp } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { normalizeTrendsResponse, type Trend, type TrendsResponse } from '@/lib/trends';
import { useTranslation } from '@/store/locale';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { OptimizedImage } from '@/components/ui/optimized-image';

export default function TrendsPage() {
  const { t } = useTranslation();
  const [season, setSeason] = useState<string>('');
  const [items, setItems] = useState<Trend[]>([]);
  const [personalized, setPersonalized] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<TrendsResponse | Trend[]>('/trends')
      .then((res) => {
        const data = normalizeTrendsResponse(res);
        setSeason(data.season);
        setItems(data.items);
        setPersonalized(Boolean(data.personalized));
      })
      .catch(() => toast.error(t('common.failed')))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="container max-w-6xl py-8">
      <div className="mb-2 flex items-center gap-2">
        <TrendingUp className="h-5 w-5 text-accent" />
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('trends.title')}</h1>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-muted-foreground">{t('trends.subtitle')}</p>
      {season && (
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="capitalize">
            {t('trends.seasonLabel')}: {season}
          </Badge>
          {personalized && (
            <Badge variant="accent">{t('trends.personalizedBadge')}</Badge>
          )}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-80" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('trends.empty')}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <Card key={item.id} className="overflow-hidden">
              {item.image_url && (
                <div className="relative h-48 w-full">
                  <OptimizedImage
                    src={item.image_url}
                    alt={item.title}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 100vw, 50vw"
                  />
                </div>
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
                <p className="text-sm text-muted-foreground line-clamp-3">{item.summary}</p>
                {item.match_reason && (
                  <p className="text-xs text-accent">{item.match_reason}</p>
                )}
                <div className="flex flex-wrap gap-1">
                  {item.tags?.slice(0, 5).map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <Button className="w-full gap-2" asChild>
                  <Link href={`/trends/${item.id}`}>
                    {t('trends.showOutfits')}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
