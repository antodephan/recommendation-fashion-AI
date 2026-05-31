'use client';

import { useRef, useState } from 'react';
import { Wand2, Star, Heart, Paperclip, X, Image as ImageIcon } from 'lucide-react';
import toast from 'react-hot-toast';
import { api, Recommendation } from '@/lib/api';
import { useTranslation } from '@/store/locale';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

export default function RecommendationsPage() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function upload(file: File) {
    const isImage =
      file.type.startsWith('image/') || /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name);
    if (!isImage) {
      toast.error(t('recommendations.uploadImagesOnly'));
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.error(t('chat.uploadTooLarge'));
      return;
    }
    setUploading(true);
    const toastId = toast.loading(t('recommendations.uploadLoading'));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post<{ url: string }>('/uploads/image', fd);
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      setImageUrl(res.url.startsWith('http') ? res.url : `${base}${res.url}`);
      toast.success(t('recommendations.uploadSuccess'), { id: toastId });
    } catch (err: any) {
      toast.error(err.message || t('recommendations.uploadFailed'), { id: toastId });
    } finally {
      setUploading(false);
    }
  }

  async function submit() {
    if (!query.trim() && !imageUrl) return;
    setLoading(true);
    try {
      const result = await api.post<Recommendation>('/recommendations', {
        query: query.trim() || t('recommendations.defaultQuery'),
        top_k: 6,
        use_weather: true,
        image_url: imageUrl?.replace(/^https?:\/\/[^/]+/, '') ?? undefined
      });
      setRec(result);
    } catch (err: any) {
      toast.error(err.message || t('recommendations.failed'));
    } finally {
      setLoading(false);
    }
  }

  async function trackEngagement(label: 'click' | 'save', outfitId?: string) {
    if (!rec?.id) return;
    try {
      await api.post('/recommendations/feedback', {
        recommendation_id: rec.id,
        rating: label === 'save' ? 5 : 1,
        label,
        comment: outfitId ? `outfit:${outfitId}` : undefined
      });
    } catch {
      /* non-blocking */
    }
  }

  async function favorite(outfitId: string) {
    try {
      await api.post(`/outfits/${outfitId}/favorite`);
      await trackEngagement('save', outfitId);
      toast.success(t('recommendations.saved'));
    } catch (err: any) {
      toast.error(err.message || t('common.failed'));
    }
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL || '';

  return (
    <div className="container max-w-5xl py-8">
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('recommendations.title')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('recommendations.subtitle')}</p>
      </div>

      <Card className="mb-8">
        <CardContent className="space-y-3 p-4">
          {imageUrl && (
            <div className="inline-flex items-center gap-3 rounded-lg border bg-card p-2 text-xs">
              <img src={imageUrl} alt="" className="h-14 w-14 rounded-md object-cover" />
              <span className="text-muted-foreground">{t('recommendations.sampleAttached')}</span>
              <button
                type="button"
                onClick={() => setImageUrl(null)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
          <div className="flex gap-3">
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept="image/*"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              disabled={uploading || loading}
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? (
                <ImageIcon className="h-4 w-4 animate-pulse" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </Button>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('recommendations.placeholder')}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
            <Button onClick={submit} disabled={loading || (!query.trim() && !imageUrl)} variant="accent">
              <Wand2 className="h-4 w-4" />
              {loading ? t('recommendations.suggesting') : t('recommendations.suggest')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-80 w-full rounded-xl" />
          ))}
        </div>
      )}

      {rec && (
        <>
          <Card className="mb-6">
            <CardContent className="space-y-2 p-6">
              <div className="flex items-center justify-between text-sm">
                <Badge variant="accent">
                  {t('recommendations.confidence')} {(rec.confidence * 100).toFixed(0)}%
                </Badge>
                <Badge variant="secondary">
                  {t('recommendations.trend')} {(rec.trend_score * 100).toFixed(0)}%
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{rec.reasoning}</p>
              {rec.weather && (
                <p className="text-xs text-muted-foreground">
                  {t('recommendations.weather')}: {rec.weather.summary} • {rec.weather.temp_c}°C •{' '}
                  {rec.weather.location}
                </p>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {rec.items.map((it) => {
              const img =
                it.image_url?.startsWith('http') || !it.image_url
                  ? it.image_url
                  : `${apiBase}${it.image_url}`;
              return (
                <Card
                  key={it.outfit_id}
                  className="cursor-pointer overflow-hidden transition-shadow hover:shadow-md"
                  onClick={() => trackEngagement('click', it.outfit_id)}
                >
                  <div className="aspect-[3/4] w-full bg-secondary">
                    {img ? (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img src={img} alt={it.name} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-muted-foreground">
                        {t('common.noImage')}
                      </div>
                    )}
                  </div>
                  <CardContent className="space-y-3 p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">{it.name}</h3>
                      <Badge variant="outline">
                        <Star className="mr-1 h-3 w-3" />
                        {(it.score * 100).toFixed(0)}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{it.why}</p>
                    <div className="flex flex-wrap gap-1">
                      {(it.tags || []).slice(0, 4).map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        favorite(it.outfit_id);
                      }}
                      className="w-full"
                      variant="outline"
                    >
                      <Heart className="h-4 w-4" /> {t('recommendations.save')}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
