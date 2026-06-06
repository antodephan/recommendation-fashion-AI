'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { Sparkles } from 'lucide-react';
import { useAuth } from '@/store/auth';
import { useTranslation } from '@/store/locale';
import { LanguageSwitcher } from '@/components/language-switcher';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function LoginPage() {
  const router = useRouter();
  const { login, loading } = useAuth();
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login(email, password);
      toast.success(t('auth.welcomeToast'));
      router.push('/chat');
    } catch (err: any) {
      toast.error(err.message || t('auth.invalidCredentials'));
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="absolute right-4 top-4">
        <LanguageSwitcher compact />
      </div>
      <Card className="w-full max-w-md">
        <CardHeader>
          <Link href="/" className="mb-4 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" />
            <span className="font-display text-xl font-semibold">Couture AI</span>
          </Link>
          <CardTitle>{t('auth.welcomeBack')}</CardTitle>
          <CardDescription>{t('auth.signInDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('auth.email')}</label>
              <Input
                required
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('auth.password')}</label>
              <Input
                required
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button type="submit" className="w-full" variant="accent" disabled={loading}>
              {loading ? t('auth.signingIn') : t('auth.signIn')}
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" /> {t('common.or')}{' '}
            <span className="h-px flex-1 bg-border" />
          </div>

          <div className="grid gap-2">
            <Button variant="outline" asChild>
              <a href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/oauth/google/login`}>
                {t('auth.continueGoogle')}
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/oauth/facebook/login`}>
                {t('auth.continueFacebook')}
              </a>
            </Button>
          </div>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            {t('auth.newHere')}{' '}
            <Link href="/register" className="font-medium text-accent hover:underline">
              {t('auth.createAccount')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
