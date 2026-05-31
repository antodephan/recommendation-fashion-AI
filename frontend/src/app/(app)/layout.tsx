'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Sparkles,
  MessageSquare,
  Heart,
  LineChart,
  Compass,
  Users,
  Settings,
  LogOut,
  Sun,
  Moon
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { useAuth } from '@/store/auth';
import { useTranslation } from '@/store/locale';
import { Button } from '@/components/ui/button';
import { LanguageSwitcher } from '@/components/language-switcher';
import { cn } from '@/lib/utils';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, hydrate, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();

  const nav = [
    { href: '/chat', label: t('nav.chat'), icon: MessageSquare },
    { href: '/recommendations', label: t('nav.recommendations'), icon: Sparkles },
    { href: '/outfits', label: t('nav.savedOutfits'), icon: Heart },
    { href: '/trends', label: t('nav.trends'), icon: Compass },
    { href: '/profile', label: t('nav.profile'), icon: Settings }
  ];

  const adminNav = [
    { href: '/admin', label: t('common.admin'), icon: Users },
    { href: '/analytics', label: t('nav.analytics'), icon: LineChart }
  ];

  useEffect(() => {
    hydrate().then(() => {
      if (!useAuth.getState().user) router.replace('/login');
    });
  }, [hydrate, router]);

  if (!user) {
    return (
      <div className="grid min-h-screen place-items-center text-muted-foreground">
        {t('common.loading')}
      </div>
    );
  }

  const isAdmin = user.role === 'admin' || user.role === 'superadmin';

  return (
    <div className="grid min-h-screen grid-cols-[260px_1fr]">
      <aside className="flex flex-col border-r bg-card/40 backdrop-blur">
        <div className="flex h-16 items-center gap-2 border-b px-5">
          <Sparkles className="h-5 w-5 text-accent" />
          <Link href="/chat" className="font-display text-lg font-semibold">
            Couture AI
          </Link>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {nav.map((n) => (
            <SidebarLink key={n.href} {...n} />
          ))}
          {isAdmin && (
            <>
              <div className="mt-6 px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('common.admin')}
              </div>
              {adminNav.map((n) => (
                <SidebarLink key={n.href} {...n} />
              ))}
            </>
          )}
        </nav>

        <div className="border-t p-3">
          <div className="mb-3 flex items-center justify-between px-2 text-sm">
            <div className="truncate">
              <div className="truncate font-medium">{user.full_name || user.email}</div>
              <div className="truncate text-xs text-muted-foreground">{user.email}</div>
            </div>
          </div>
          <div className="mb-3 px-1">
            <LanguageSwitcher compact />
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              aria-label={t('nav.toggleTheme')}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              className="flex-1 justify-start"
              onClick={async () => {
                await logout();
                router.push('/login');
              }}
            >
              <LogOut className="h-4 w-4" /> {t('nav.signOut')}
            </Button>
          </div>
        </div>
      </aside>

      <main className="overflow-hidden">{children}</main>
    </div>
  );
}

function SidebarLink({
  href,
  label,
  icon: Icon
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors',
        'hover:bg-secondary hover:text-foreground'
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}
