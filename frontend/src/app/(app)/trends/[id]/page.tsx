'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { api, APIError } from '@/lib/api';
import type { Trend } from '@/lib/trends';
import { useTranslation } from '@/store/locale';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { OptimizedImage } from '@/components/ui/optimized-image';
import {
  OutfitRecommendationCards,
  type OutfitRecPayload
} from '@/components/chat/outfit-recommendation-cards';

export default function TrendDetailPage() {
  const params = useParams();
  const trendId = String(params.id);
  const { t } = useTranslation();
  const toastShown = useRef(false);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [outfits, setOutfits] = useState<OutfitRecPayload | null>(null);
  const [loadingTrend, setLoadingTrend] = useState(true);
  const [loadingOutfits, setLoadingOutfits] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    toastShown.current = false;
    setLoadError(null);
    setLoadingTrend(true);
    setLoadingOutfits(true);
    setTrend(null);
    setOutfits(null);

    const trendReq = api.get<Trend>(`/trends/${trendId}`);
    const outfitsReq = api.get<OutfitRecPayload & { trend_id: string; title: string }>(
      `/trends/${trendId}/outfits`
    );

    trendReq
      .then((trendData) => {
        if (cancelled) return;
        setTrend(trendData);
      })
      .catch((err) => {
        if (cancelled || toastShown.current) return;
        toastShown.current = true;
        const message =
          err instanceof APIError && err.status === 404
            ? t('trends.notFound')
            : t('trends.loadFailed');
        setLoadError(message);
        toast.error(message);
      })
      .finally(() => {
        if (!cancelled) setLoadingTrend(false);
      });

    outfitsReq
      .then((outfitData) => {
        if (cancelled) return;
        setOutfits(outfitData);
      })
      .catch(() => {
        if (cancelled) return;
        setOutfits(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingOutfits(false);
      });

    return () => {
      cancelled = true;
    };
  }, [trendId, t]);

  return (
    <div className="container max-w-4xl py-8">
      <Button variant="ghost" className="mb-6 gap-2 px-0" asChild>
        <Link href="/trends">
          <ArrowLeft className="h-4 w-4" />
          {t('trends.backToList')}
        </Link>
      </Button>

      {loadingTrend ? (
        <Skeleton className="mb-8 h-72 w-full" />
      ) : loadError ? (
        <p className="text-sm text-destructive">{loadError}</p>
      ) : trend ? (
        <Card className="mb-8 overflow-hidden">
          {trend.image_url && (
            <div className="relative h-56 w-full md:h-72">
              <OptimizedImage
                src={trend.image_url}
                alt={trend.title}
                fill
                className="object-cover"
                sizes="(max-width: 768px) 100vw, 896px"
                priority
              />
            </div>
          )}
          <CardContent className="space-y-4 p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="font-display text-3xl font-bold tracking-tight">{trend.title}</h1>
                <p className="text-sm text-muted-foreground">{trend.source}</p>
              </div>
              <Badge variant="accent" title={t('trends.popularityHint')}>
                {Math.round(trend.popularity * 100)}%
              </Badge>
            </div>
            <p className="text-muted-foreground">{trend.summary}</p>
            <div className="flex flex-wrap gap-2">
              {trend.season && (
                <Badge variant="secondary" className="capitalize">
                  {t('trends.seasonLabel')}: {trend.season}
                </Badge>
              )}
              {trend.tags?.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">{t('trends.notFound')}</p>
      )}

      {!loadError && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" />
            <h2 className="font-display text-xl font-semibold">{t('trends.outfitsTitle')}</h2>
          </div>
          {loadingOutfits ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          ) : outfits?.items?.length ? (
            <OutfitRecommendationCards data={outfits} />
          ) : (
            <p className="text-sm text-muted-foreground">
              {outfits?.reasoning || t('trends.noOutfits')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
