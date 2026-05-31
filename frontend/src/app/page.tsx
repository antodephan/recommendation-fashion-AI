'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { LanguageSwitcher } from '@/components/language-switcher';
import { useTranslation } from '@/store/locale';
import { Sparkles, MessageSquare, Compass, Wand2, ArrowRight } from 'lucide-react';

export default function LandingPage() {
  const { t } = useTranslation();

  const features = [
    {
      icon: MessageSquare,
      title: t('landing.feature1Title'),
      body: t('landing.feature1Body')
    },
    {
      icon: Compass,
      title: t('landing.feature2Title'),
      body: t('landing.feature2Body')
    },
    {
      icon: Wand2,
      title: t('landing.feature3Title'),
      body: t('landing.feature3Body')
    }
  ];

  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <div className="absolute inset-0 glow pointer-events-none" />
      <header className="container flex flex-wrap items-center justify-between gap-4 py-6">
        <Link href="/" className="flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-accent" />
          <span className="font-display text-2xl font-bold tracking-tight">Couture AI</span>
        </Link>
        <nav className="hidden items-center gap-6 lg:flex">
          <Link href="/trends" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.trends')}
          </Link>
          <Link href="/chat" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.chat')}
          </Link>
          <Link href="/recommendations" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.recommendations')}
          </Link>
        </nav>
        <div className="flex items-center gap-3">
          <LanguageSwitcher compact />
          <Button asChild variant="ghost">
            <Link href="/login">{t('nav.signIn')}</Link>
          </Button>
          <Button asChild variant="accent">
            <Link href="/register">{t('nav.getStarted')}</Link>
          </Button>
        </div>
      </header>

      <section className="container relative pt-12 pb-24 md:pt-24 md:pb-32 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="font-display text-5xl md:text-7xl font-bold leading-[1.05] tracking-tight"
        >
          {t('landing.heroTitle')}{' '}
          <span className="text-accent">{t('landing.heroHighlight')}</span>{' '}
          {t('landing.heroTitleEnd')}
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground"
        >
          {t('landing.heroSubtitle')}
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-10 flex flex-wrap justify-center gap-4"
        >
          <Button asChild size="lg" variant="accent">
            <Link href="/register">
              {t('landing.startChatting')} <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/trends">{t('landing.exploreTrends')}</Link>
          </Button>
        </motion.div>
      </section>

      <section className="container grid gap-6 pb-24 md:grid-cols-3">
        {features.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            <Card>
              <CardContent className="p-8">
                <f.icon className="mb-4 h-8 w-8 text-accent" />
                <h3 className="font-display text-xl font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </section>

      <footer className="border-t py-8">
        <div className="container flex flex-col items-center justify-between gap-4 text-sm text-muted-foreground md:flex-row">
          <span>{t('landing.footer')}</span>
          <div className="flex gap-6">
            <Link href="/docs/ARCHITECTURE.md">{t('common.architecture')}</Link>
            <Link href="/admin">{t('common.admin')}</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
