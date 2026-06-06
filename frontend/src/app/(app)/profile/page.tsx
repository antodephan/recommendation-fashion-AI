'use client';

import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Input, Textarea } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LanguageSwitcher } from '@/components/language-switcher';
import { api, User } from '@/lib/api';
import { useAuth } from '@/store/auth';
import { useTranslation } from '@/store/locale';

function normalizeProfileGender(gender?: string | null): string {
  const g = (gender || '').trim().toLowerCase();
  if (['male', 'nam', 'm', 'men', 'man'].includes(g)) return 'male';
  if (['female', 'nu', 'nữ', 'f', 'women', 'woman'].includes(g)) return 'female';
  return '';
}

export default function ProfilePage() {
  const { user, hydrate } = useAuth();
  const { t, locale } = useTranslation();
  const [form, setForm] = useState<Partial<User>>({});
  const [colors, setColors] = useState('');
  const [brands, setBrands] = useState('');
  const [styles, setStyles] = useState('');
  const [budget, setBudget] = useState<number | undefined>();

  useEffect(() => {
    if (!user) return;
    setForm({ ...user, gender: normalizeProfileGender(user.gender) || undefined });
    setColors((user.preferences?.colors || []).join(', '));
    setBrands((user.preferences?.brands || []).join(', '));
    setStyles((user.preferences?.styles || []).join(', '));
    setBudget(user.preferences?.budget);
  }, [user]);

  async function save() {
    try {
      await api.patch<User>('/users/me', {
        full_name: form.full_name,
        gender: form.gender,
        body_type: form.body_type,
        height_cm: form.height_cm,
        weight_kg: form.weight_kg,
        location: form.location,
        locale,
        preferences: {
          colors: colors.split(',').map((s) => s.trim()).filter(Boolean),
          brands: brands.split(',').map((s) => s.trim()).filter(Boolean),
          styles: styles.split(',').map((s) => s.trim()).filter(Boolean),
          budget
        }
      });
      await hydrate();
      toast.success(t('profile.updated'));
    } catch (err: any) {
      toast.error(err.message || t('common.failed'));
    }
  }

  if (!user) return null;

  return (
    <div className="container max-w-3xl py-8">
      <h1 className="mb-6 font-display text-3xl font-bold tracking-tight">{t('profile.title')}</h1>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>{t('profile.language')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <LanguageSwitcher />
          <p className="text-sm text-muted-foreground">{t('profile.languageHint')}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('profile.basics')}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label={t('profile.fullName')}>
            <Input
              value={form.full_name || ''}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </Field>
          <Field label={t('profile.location')}>
            <Input
              value={form.location || ''}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="Paris, FR"
            />
          </Field>
          <Field label={t('profile.gender')}>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={form.gender || ''}
              onChange={(e) => setForm({ ...form, gender: e.target.value || undefined })}
            >
              <option value="">{t('profile.genderUnspecified')}</option>
              <option value="male">{t('profile.genderMale')}</option>
              <option value="female">{t('profile.genderFemale')}</option>
            </select>
          </Field>
          <Field label={t('profile.bodyType')}>
            <Input
              value={form.body_type || ''}
              onChange={(e) => setForm({ ...form, body_type: e.target.value })}
              placeholder="hourglass / athletic / pear …"
            />
          </Field>
          <Field label={t('profile.height')}>
            <Input
              type="number"
              value={form.height_cm ?? ''}
              onChange={(e) => setForm({ ...form, height_cm: e.target.value ? +e.target.value : null })}
            />
          </Field>
          <Field label={t('profile.weight')}>
            <Input
              type="number"
              value={form.weight_kg ?? ''}
              onChange={(e) => setForm({ ...form, weight_kg: e.target.value ? +e.target.value : null })}
            />
          </Field>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>{t('profile.preferences')}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Field label={t('profile.colors')}>
            <Input value={colors} onChange={(e) => setColors(e.target.value)} placeholder="black, cream, navy" />
          </Field>
          <Field label={t('profile.brands')}>
            <Input value={brands} onChange={(e) => setBrands(e.target.value)} placeholder="COS, Acne Studios" />
          </Field>
          <Field label={t('profile.styles')}>
            <Input value={styles} onChange={(e) => setStyles(e.target.value)} placeholder="minimalist, smart-casual" />
          </Field>
          <Field label={t('profile.budget')}>
            <Input
              type="number"
              value={budget ?? ''}
              onChange={(e) => setBudget(e.target.value ? +e.target.value : undefined)}
            />
          </Field>
        </CardContent>
      </Card>

      <div className="mt-6 flex justify-end">
        <Button variant="accent" onClick={save}>
          {t('profile.saveProfile')}
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}
