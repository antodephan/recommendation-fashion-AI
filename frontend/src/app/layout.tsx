import type { Metadata } from 'next';
import { Be_Vietnam_Pro, Inter, Playfair_Display } from 'next/font/google';
import './globals.css';
import { ThemeProvider } from '@/components/theme-provider';
import { LocaleProvider } from '@/components/locale-provider';
import { Toaster } from 'react-hot-toast';

const inter = Inter({
  subsets: ['latin', 'latin-ext', 'vietnamese'],
  variable: '--font-en-sans',
  display: 'swap'
});

const playfair = Playfair_Display({
  subsets: ['latin', 'vietnamese'],
  variable: '--font-en-display',
  display: 'swap'
});

const beVietnamPro = Be_Vietnam_Pro({
  subsets: ['vietnamese', 'latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-vi',
  display: 'swap'
});

export const metadata: Metadata = {
  title: 'Couture AI — Your Personal Fashion Stylist',
  description:
    'Conversational AI that learns your taste and recommends outfits curated for you — powered by RAG and vector search.',
  metadataBase: new URL('http://localhost:3000')
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${playfair.variable} ${beVietnamPro.variable}`}
    >
      <body className="min-h-screen overflow-x-hidden bg-background font-sans antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <LocaleProvider>
            {children}
          </LocaleProvider>
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: 'hsl(240 10% 6%)',
                color: '#fff',
                border: '1px solid hsl(240 4% 18%)'
              }
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
