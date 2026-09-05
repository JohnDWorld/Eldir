/**
 * Spark - sparkline minimaliste sans dépendance, largeur fluide.
 * Cf. DA/shared.jsx · Spark.
 */

import { cn } from '@/lib/utils';

interface SparkProps {
  data: readonly number[];
  width?: number;
  height?: number;
  fill?: string | undefined;
  stroke?: string;
  className?: string;
}

export function Spark({
  data,
  width = 60,
  height = 18,
  fill,
  stroke = 'hsl(var(--eldir-orange))',
  className,
}: SparkProps): JSX.Element {
  if (data.length < 2) {
    return <svg className={cn('h-4 w-full', className)} aria-hidden />;
  }
  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / span) * (height - 2) - 1;
      return `${x},${y}`;
    })
    .join(' ');
  const area = `0,${height} ${points} ${width},${height}`;

  // Largeur fluide : `width`/`height` ne servent plus qu'au calcul des
  // coordonnées. Une taille fixe débordait de sa colonne sur mobile et
  // provoquait un scroll horizontal de toute la page.
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn('h-4 w-full', className)}
      role="img"
      aria-label="sparkline"
    >
      {fill && <polygon points={area} fill={fill} />}
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.4}
        vectorEffect="non-scaling-stroke"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
