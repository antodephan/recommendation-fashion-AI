'use client';

import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Users } from 'lucide-react';
import { api, User } from '@/lib/api';
import { useTranslation } from '@/store/locale';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { formatDate, cn } from '@/lib/utils';
import {
  InsightsOverview,
  UserTrendsCharts,
  FashionTrendsCharts,
  HmSyncPanel
} from '@/components/admin/admin-insights';

type Tab = 'overview' | 'user-trends' | 'fashion-trends' | 'hm-sync' | 'users';

export default function AdminPage() {
  const { t } = useTranslation();
  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: t('admin.overview') },
    { id: 'user-trends', label: t('admin.userTrends') },
    { id: 'fashion-trends', label: t('admin.fashionTrends') },
    { id: 'hm-sync', label: t('admin.hmSync') },
    { id: 'users', label: t('admin.users') }
  ];
  const [tab, setTab] = useState<Tab>('overview');
  const [overview, setOverview] = useState<any>(null);
  const [dau, setDau] = useState<any[]>([]);
  const [recSeries, setRecSeries] = useState<any[]>([]);
  const [popularStyles, setPopularStyles] = useState<any[]>([]);
  const [userTrends, setUserTrends] = useState<any>(null);
  const [fashionTrends, setFashionTrends] = useState<any>(null);
  const [syncHistory, setSyncHistory] = useState<any[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [q, setQ] = useState('');
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [ov, dauData, recData, styles, ut, ft, sync, page] = await Promise.all([
        api.get('/admin/insights/overview'),
        api.get('/analytics/dau'),
        api.get('/admin/insights/recommendations?days=30'),
        api.get('/analytics/popular-styles'),
        api.get('/admin/insights/user-trends'),
        api.get('/admin/insights/fashion-trends'),
        api.get('/admin/insights/hm-sync?days=30'),
        api.get<{ items: User[] }>('/admin/users?page=1&page_size=25')
      ]);
      setOverview(ov);
      setDau(dauData);
      setRecSeries(recData);
      setPopularStyles(
        (styles as any[]).map((r) => ({ name: r.name ?? r.style ?? '', favorites: r.favorites }))
      );
      setUserTrends(ut);
      setFashionTrends(ft);
      setSyncHistory(sync);
      setUsers(page.items);
    } catch (err: any) {
      toast.error(err.message || t('admin.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  async function search() {
    const page = await api.get<{ items: User[] }>(`/admin/users?q=${encodeURIComponent(q)}`);
    setUsers(page.items);
  }

  async function toggleRole(user: User) {
    const newRole = user.role === 'admin' ? 'user' : 'admin';
    await api.patch<User>(`/admin/users/${user.id}`, { role: newRole });
    toast.success(`Role changed to ${newRole}`);
    load();
  }

  async function syncCatalog() {
    setSyncing(true);
    try {
      const res = await api.post<{ message: string }>('/admin/hm/sync-catalog');
      toast.success(res.message);
      load();
    } catch (err: any) {
      toast.error(err.message || t('admin.syncFailed'));
    } finally {
      setSyncing(false);
    }
  }

  async function syncTrends() {
    setSyncing(true);
    try {
      const res = await api.post<{ message: string }>('/admin/hm/sync-trends');
      toast.success(res.message);
      load();
    } catch (err: any) {
      toast.error(err.message || t('admin.syncFailed'));
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="container max-w-6xl py-8">
      <div className="mb-6 flex items-center gap-2">
        <Users className="h-5 w-5 text-accent" />
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('admin.title')}</h1>
      </div>

      <div className="mb-6 flex flex-wrap gap-2 border-b pb-2">
        {TABS.map((tabItem) => (
          <button
            key={tabItem.id}
            type="button"
            onClick={() => setTab(tabItem.id)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              tab === tabItem.id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-secondary'
            )}
          >
            {tabItem.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <InsightsOverview overview={overview} dau={dau} recSeries={recSeries} popularStyles={popularStyles} />
      )}
      {tab === 'user-trends' && <UserTrendsCharts data={userTrends} />}
      {tab === 'fashion-trends' && <FashionTrendsCharts data={fashionTrends} />}
      {tab === 'hm-sync' && (
        <HmSyncPanel
          history={syncHistory}
          onSyncCatalog={syncCatalog}
          onSyncTrends={syncTrends}
          syncing={syncing}
        />
      )}
      {tab === 'users' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>{t('admin.users')}</span>
              <div className="flex gap-2">
                <Input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder={t('admin.searchUsers')}
                  className="w-64"
                />
                <Button onClick={search} variant="outline">
                  {t('common.search')}
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="p-2">Email</th>
                    <th className="p-2">Name</th>
                    <th className="p-2">Role</th>
                    <th className="p-2">Active</th>
                    <th className="p-2">Joined</th>
                    <th className="p-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-t">
                      <td className="p-2 font-medium">{u.email}</td>
                      <td className="p-2">{u.full_name || '—'}</td>
                      <td className="p-2">
                        <Badge
                          variant={
                            u.role === 'superadmin' ? 'accent' : u.role === 'admin' ? 'default' : 'secondary'
                          }
                        >
                          {u.role}
                        </Badge>
                      </td>
                      <td className="p-2">{u.is_active ? 'Yes' : 'No'}</td>
                      <td className="p-2 text-muted-foreground">{formatDate(u.created_at)}</td>
                      <td className="p-2">
                        <Button size="sm" variant="outline" onClick={() => toggleRole(u)}>
                          Toggle admin
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
