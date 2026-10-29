/**
 * Les messages acceptés par le serveur que le fil ne porte pas encore.
 *
 * Depuis que la route de message rend la main sans attendre la fin du tour,
 * le champ de saisie ne se verrouille plus : écrire à un agent qui travaille
 * est le geste qui le débloque. Il faut donc montrer ce qui attend.
 *
 * Sans ce filtre, un message réapparaîtrait en double le temps que l'event
 * `user_message` remonte par WebSocket. On retire une copie par event et pas
 * toutes les copies identiques : envoyer deux fois « ok » doit laisser le
 * second à l'écran tant qu'un seul des deux est revenu.
 */
export function messagesEnAttente(
  envoyes: string[],
  evenements: { type: string; data?: { text?: unknown } | null }[],
): string[] {
  const restants = [...envoyes];
  for (const e of evenements) {
    if (e.type !== 'user_message') continue;
    const texte = e.data?.text;
    if (typeof texte !== 'string') continue;
    const i = restants.indexOf(texte);
    if (i !== -1) restants.splice(i, 1);
  }
  return restants;
}
