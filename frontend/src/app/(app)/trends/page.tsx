'use client';

import { useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { api } from '@/lib/api';
import { useTranslation } from '@/store/locale';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

type Trend = {
  id: string;
  title: string;
  summary: string;
  image_url?: string;
  source?: string;
  source_url?: string;
  tags: string[];
  season?: string;
  popularity: number;
  published_at?: string;
};

export default function TrendsPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Trend[]>('/trends')
      .then(setItems)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="container max-w-6xl py-8">
      <div className="mb-6 flex items-center gap-2">
        <TrendingUp className="h-5 w-5 text-accent" />
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('trends.title')}</h1>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Card key={item.id} className="overflow-hidden">
              {item.image_url && (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={item.image_url} alt={item.title} className="h-44 w-full object-cover" />
              )}
              <CardContent className="space-y-2 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">{item.title}</h3>
                  <Badge variant="accent">{(item.popularity * 100).toFixed(0)}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{item.summary}</p>
                <div className="flex flex-wrap gap-1">
                  {item.tags?.slice(0, 4).map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {item.source} • {item.season}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
