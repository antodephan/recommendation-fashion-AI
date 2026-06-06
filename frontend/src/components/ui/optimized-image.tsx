'use client';

import Image from 'next/image';

type OptimizedImageProps = {
  src: string;
  alt: string;
  className?: string;
  priority?: boolean;
  fill?: boolean;
  width?: number;
  height?: number;
  sizes?: string;
};

function canUseNextImage(src: string): boolean {
  try {
    const host = new URL(src).hostname;
    return (
      host.includes('unsplash.com') ||
      host.includes('hm.com') ||
      host.includes('couture.ai') ||
      host === 'localhost'
    );
  } catch {
    return false;
  }
}

export function OptimizedImage({
  src,
  alt,
  className,
  priority = false,
  fill = false,
  width,
  height,
  sizes = '(max-width: 768px) 100vw, 50vw'
}: OptimizedImageProps) {
  if (!src) return null;

  if (canUseNextImage(src)) {
    if (fill) {
      return (
        <Image
          src={src}
          alt={alt}
          fill
          className={className}
          sizes={sizes}
          priority={priority}
          loading={priority ? undefined : 'lazy'}
        />
      );
    }
    return (
      <Image
        src={src}
        alt={alt}
        width={width ?? 400}
        height={height ?? 500}
        className={className}
        sizes={sizes}
        priority={priority}
        loading={priority ? undefined : 'lazy'}
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className={className}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      width={width}
      height={height}
    />
  );
}
