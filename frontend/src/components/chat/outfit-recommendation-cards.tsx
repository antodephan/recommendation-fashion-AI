'use client';

import { ExternalLink } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export type OutfitRecItem = {
  outfit_id: string;
  name: string;
  image_url?: string | null;
  score: number;
  why: string;
  tags?: string[];
  price?: number | null;
  currency?: string;
  source_url?: string | null;
};

export type OutfitRecPayload = {
  reasoning?: string;
  confidence?: number;
  items: OutfitRecItem[];
};

export function OutfitRecommendationCards({ data }: { data: OutfitRecPayload }) {
  if (!data?.items?.length) return null;

  return (
    <div className="mt-4 space-y-3 border-t pt-4">
      {data.reasoning && (
        <p className="text-xs text-muted-foreground italic">{data.reasoning}</p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {data.items.map((item) => (
          <Card key={item.outfit_id} className="overflow-hidden">
            {item.image_url && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={item.image_url} alt={item.name} className="h-40 w-full object-cover" />
            )}
            <CardContent className="space-y-1 p-3">
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-semibold leading-tight">{item.name}</h4>
                {item.price != null && (
                  <Badge variant="accent">
                    {item.price.toFixed(0)} {item.currency || 'USD'}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2">{item.why}</p>
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                >
                  View on H&M <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
