/**
 * Formatage des valeurs affichées. Un seul endroit : `formatTokens` existait
 * en trois copies identiques, et les coûts se montraient tantôt à deux
 * décimales, tantôt à quatre, sur la même page.
 */

/** 1 234 → « 1.2k ». Les ordres de grandeur suffisent à l'écran. */
export function formatTokens(n: number): string {
  if (n === 0) return '0';
  if (n < 1_000) return String(n);
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

/**
 * Coût en dollars. La précision suit le montant : à 0,08 $ les centimes ne
 * disent rien, à 12 $ les dix-millièmes sont du bruit.
 */
export function formatCost(usd: number): string {
  if (usd === 0) return '$0';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

/**
 * Âge d'une session, en français et sans ambiguïté.
 *
 * L'ancien format `HH:MM` affichait « 00:35 » pour trente-cinq minutes (on
 * lisait trente-cinq secondes) et « 48:01 » pour deux jours.
 */
export function formatAge(iso: string): string {
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.floor(minutes / 60);
  if (heures < 24) return `il y a ${heures} h`;
  const jours = Math.floor(heures / 24);
  return jours === 1 ? 'hier' : `il y a ${jours} j`;
}

/** Date courte et lisible : « 23 oct ». */
export function formatDayShort(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

/** Date et heure complètes, pour un `title` ou une fiche de détail. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}
