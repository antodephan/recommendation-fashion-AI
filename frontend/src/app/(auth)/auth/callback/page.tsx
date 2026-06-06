'use client';

import { Suspense, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { Sparkles } from 'lucide-react';
import { useAuth } from '@/store/auth';
import { useTranslation } from '@/store/locale';

function OAuthCallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { setTokens, hydrate } = useAuth();
  const { t } = useTranslation();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const error = params.get('error');
    if (error) {
      toast.error(decodeURIComponent(error));
      router.replace('/login');
      return;
    }

    const access = params.get('access_token');
    const refresh = params.get('refresh_token');
    if (!access || !refresh) {
      toast.error(t('auth.oauthFailed'));
      router.replace('/login');
      return;
    }

    setTokens(access, refresh);
    hydrate()
      .then(() => {
        toast.success(t('auth.welcomeToast'));
        router.replace('/chat');
      })
      .catch(() => {
        toast.error(t('auth.oauthFailed'));
        router.replace('/login');
      });
  }, [params, router, setTokens, hydrate, t]);

  return (
    <div className="grid min-h-screen place-items-center text-muted-foreground">
      {t('auth.oauthSigningIn')}
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-screen place-items-center text-muted-foreground">
          <Sparkles className="mb-2 h-6 w-6 animate-pulse text-accent" />
        </div>
      }
    >
      <OAuthCallbackInner />
    </Suspense>
  );
}
