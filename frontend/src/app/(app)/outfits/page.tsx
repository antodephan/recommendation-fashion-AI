'use client';

import { useEffect, useState } from 'react';
import { Heart, HeartOff } from 'lucide-react';
import toast from 'react-hot-toast';
import Link from 'next/link';
import { api, Outfit } from '@/lib/api';
import { useTranslation } from '@/store/locale';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export default function SavedOutfitsPage() {
  const { t } = useTranslation();
  const [favorites, setFavorites] = useState<Outfit[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Outfit[]>('/outfits/me/favorites')
      .then((d) => setFavorites(d))
      .finally(() => setLoading(false));
  }, []);

  async function remove(id: string) {
    try {
      await api.post(`/outfits/${id}/favorite`);
      setFavorites((p) => p.filter((o) => o.id !== id));
      toast.success(t('outfits.removed'));
    } catch {
      toast.error(t('common.failed'));
    }
  }

  return (
    <div className="container max-w-5xl py-8">
      <div className="mb-6 flex items-center gap-2">
        <Heart className="h-5 w-5 text-accent" />
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('outfits.title')}</h1>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-80 w-full" />
          ))}
        </div>
      ) : favorites.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t('outfits.empty')}{' '}
          <Link href="/recommendations" className="text-accent underline">
            {t('outfits.emptyLink')}
          </Link>{' '}
          {t('outfits.emptyEnd')}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {favorites.map((o) => (
            <Card key={o.id} className="overflow-hidden">
              <div className="aspect-[3/4] bg-secondary">
                {o.image_url && (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={o.image_url} alt={o.name} className="h-full w-full object-cover" />
                )}
              </div>
              <CardContent className="space-y-2 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">{o.name}</h3>
                  <Badge variant="outline">{o.style}</Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">{o.description}</p>
                <div className="flex flex-wrap gap-1">
                  {(o.tags || []).slice(0, 4).map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <Button onClick={() => remove(o.id)} variant="outline" className="w-full">
                  <HeartOff className="h-4 w-4" /> {t('common.remove')}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
