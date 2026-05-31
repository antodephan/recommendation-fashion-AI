'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  CartesianGrid,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { useTranslation } from '@/store/locale';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const tooltipStyles = {
  background: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))'
};

const COLORS = ['hsl(var(--accent))', '#8884d8', '#82ca9d', '#ffc658', '#ff8042'];

type OverviewData = {
  users: { total: number; new_24h: number };
  recommendations: { total: number; last_24h: number };
  favorites: number;
  outfits: number;
  ai: { tokens_24h: number; cost_7d: number };
  hm: {
    products: number;
    trends: number;
    last_sync_at: string | null;
    last_sync_region: string | null;
    last_sync_status?: string | null;
    last_sync_error?: string | null;
  };
  chat_to_recommendation_rate: number;
  ctr: number;
};

type DauPoint = { day: string; dau: number };
type RecPoint = { day: string; count: number; avg_confidence: number; avg_trend: number };

export function InsightsOverview({
  overview,
  dau,
  recSeries,
  popularStyles
}: {
  overview: OverviewData | null;
  dau: DauPoint[];
  recSeries: RecPoint[];
  popularStyles: Array<{ name: string; favorites: number }>;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4 lg:grid-cols-6">
        <Stat title={t('admin.hmProducts')} value={overview?.hm.products ?? '—'} />
        <Stat title={t('admin.hmTrends')} value={overview?.hm.trends ?? '—'} />
        <Stat title={t('admin.usersTotal')} value={overview?.users.total ?? '—'} sub={`+${overview?.users.new_24h ?? 0} today`} />
        <Stat title={t('admin.recs24h')} value={overview?.recommendations.last_24h ?? '—'} />
        <Stat title={t('admin.chatToRec')} value={`${((overview?.chat_to_recommendation_rate ?? 0) * 100).toFixed(0)}%`} />
        <Stat title={t('admin.ctr')} value={`${((overview?.ctr ?? 0) * 100).toFixed(1)}%`} />
      </div>

      {overview?.hm.last_sync_at && (
        <p className="text-sm text-muted-foreground">
          {t('admin.lastSync')}: {new Date(overview.hm.last_sync_at).toLocaleString()} ({overview.hm.last_sync_region})
          {overview.hm.last_sync_status ? ` — ${overview.hm.last_sync_status}` : ''}
        </p>
      )}
      {overview?.hm.last_sync_error && (
        <p className="text-sm text-destructive">Last sync error: {overview.hm.last_sync_error}</p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recommendations (30d)</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={recSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyles} />
                <Line type="monotone" dataKey="count" stroke="hsl(var(--accent))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Daily Active Users (14d)</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dau}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyles} />
                <Line type="monotone" dataKey="dau" stroke="#8884d8" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Most Favorited Styles</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={popularStyles}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyles} />
              <Bar dataKey="favorites" fill="hsl(var(--accent))" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ title, value, sub }: { title: string; value: number | string; sub?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{title}</div>
        <div className="mt-1 font-display text-2xl font-bold">{value}</div>
        {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export function UserTrendsCharts({
  data
}: {
  data: {
    top_colors: Array<{ name: string; count: number }>;
    top_styles: Array<{ name: string; count: number }>;
    top_brands: Array<{ name: string; count: number }>;
    locations: Array<{ name: string; count: number }>;
    preference_signals: Array<{ day: string; count: number }>;
    budget_avg: number | null;
  } | null;
}) {
  if (!data) return null;
  return (
    <div className="space-y-6">
      {data.budget_avg != null && (
        <p className="text-sm text-muted-foreground">Average user budget: {data.budget_avg.toFixed(0)}</p>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        <BarBlock title="Top Colors" data={data.top_colors} />
        <BarBlock title="Top Styles" data={data.top_styles} />
        <BarBlock title="Top Brands" data={data.top_brands} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>User Locations</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.locations} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={90} label>
                  {data.locations.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyles} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Preference Signals (14d)</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.preference_signals}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyles} />
                <Line type="monotone" dataKey="count" stroke="hsl(var(--accent))" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function BarBlock({ title, data }: { title: string; data: Array<{ name: string; count: number }> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8 }}>
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={tooltipStyles} />
            <Bar dataKey="count" fill="hsl(var(--accent))" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function FashionTrendsCharts({
  data
}: {
  data: {
    ranking: Array<{ title: string; popularity: number; season?: string }>;
    by_season: Array<{ name: string; count: number }>;
    top_tags: Array<{ name: string; count: number }>;
    timeline: Array<{ day: string; count: number }>;
  } | null;
}) {
  if (!data) return null;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Trend Popularity</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.ranking.slice(0, 10)} layout="vertical" margin={{ left: 16 }}>
                <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="title" width={120} tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={tooltipStyles} />
                <Bar dataKey="popularity" fill="#8884d8" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Trends by Season</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.by_season} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                  {data.by_season.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyles} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <BarBlock title="Popular Tags" data={data.top_tags} />
    </div>
  );
}

export function HmSyncPanel({
  history,
  onSyncCatalog,
  onSyncTrends,
  syncing
}: {
  history: Array<{
    id: string;
    job_type: string;
    status: string;
    region: string | null;
    items_added: number;
    items_updated: number;
    items_failed: number;
    duration_ms: number;
    created_at: string;
    error_message?: string | null;
  }>;
  onSyncCatalog: () => void;
  onSyncTrends: () => void;
  syncing: boolean;
}) {
  const { t } = useTranslation();
  const chartData = history.map((h) => ({
    day: new Date(h.created_at).toLocaleDateString(),
    added: h.items_added,
    updated: h.items_updated,
    job: h.job_type
  }));

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <button
          type="button"
          disabled={syncing}
          onClick={onSyncCatalog}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground disabled:opacity-50"
        >
          {t('admin.syncCatalogBtn')}
        </button>
        <button
          type="button"
          disabled={syncing}
          onClick={onSyncTrends}
          className="rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {t('admin.syncTrendsBtn')}
        </button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t('admin.syncHistory')}</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="day" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={tooltipStyles} />
              <Bar dataKey="added" stackId="a" fill="hsl(var(--accent))" />
              <Bar dataKey="updated" stackId="a" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-secondary/50 text-left text-muted-foreground">
            <tr>
              <th className="p-2">Time</th>
              <th className="p-2">Job</th>
              <th className="p-2">Status</th>
              <th className="p-2">Region</th>
              <th className="p-2">+ / ~ / !</th>
              <th className="p-2">Duration</th>
              <th className="p-2">Error</th>
            </tr>
          </thead>
          <tbody>
            {history
              .slice()
              .reverse()
              .map((h) => (
                <tr key={h.id} className="border-t">
                  <td className="p-2">{new Date(h.created_at).toLocaleString()}</td>
                  <td className="p-2">{h.job_type}</td>
                  <td className="p-2">{h.status}</td>
                  <td className="p-2">{h.region || '—'}</td>
                  <td className="p-2">
                    {h.items_added} / {h.items_updated} / {h.items_failed}
                  </td>
                  <td className="p-2">{(h.duration_ms / 1000).toFixed(1)}s</td>
                  <td className="p-2 max-w-xs truncate" title={h.error_message || undefined}>
                    {h.error_message || '—'}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
