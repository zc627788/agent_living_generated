"use client";

import Image from "next/image";
import { useMemo, useState } from "react";

type ThumbnailPreviewProps = {
  src?: string | null;
  alt: string;
  className?: string;
};

function getAbbr(value: string) {
  const clean = value.trim();
  if (!clean) return "KB";
  return clean.slice(0, 2).toUpperCase();
}

export function ThumbnailPreview({ src, alt, className }: ThumbnailPreviewProps) {
  const [broken, setBroken] = useState(false);
  const fallbackText = useMemo(() => getAbbr(alt), [alt]);

  if (!src || broken) {
    return (
      <div className={`thumbnail-fallback ${className ?? ""}`.trim()} aria-label={alt}>
        <span>{fallbackText}</span>
      </div>
    );
  }

  return (
    <Image
      src={src}
      alt={alt}
      className={`thumbnail-image ${className ?? ""}`.trim()}
      width={320}
      height={180}
      unoptimized
      onError={() => setBroken(true)}
    />
  );
}
