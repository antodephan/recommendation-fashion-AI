import { Skeleton } from '@/components/ui/skeleton';

export default function AppLoading() {
  return (
    <div className="container max-w-6xl py-8">
      <Skeleton className="mb-4 h-10 w-64" />
      <Skeleton className="mb-8 h-5 w-96" />
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    </div>
  );
}
