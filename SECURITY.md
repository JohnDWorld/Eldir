# Signaler une vulnérabilité

Eldir est self-hosted : il tient des jetons Git, des identifiants Claude, une
porte de publication et, depuis la surface d'agent extérieur, des jetons de dix
ans. Une faille ici touche le dépôt de quelqu'un, pas un service central.

## Où écrire

**[Ouvre un signalement privé sur GitHub](https://github.com/JohnDWorld/Eldir/security/advisories/new)**
(onglet *Security* du dépôt, « Report a vulnerability »).

C'est le seul canal. **N'ouvre pas d'issue publique** pour une faille : une issue
est lisible par tout le monde, y compris par celui qui n'a pas encore mis à jour
son instance. Le signalement privé reste entre toi et le mainteneur jusqu'à ce
qu'un correctif existe.

Si tu n'as pas de compte GitHub, ouvre une issue publique qui dit seulement
« j'ai une faille à signaler, comment te joindre ? », sans aucun détail.

## Ce qu'on promet

Eldir est maintenu par une personne, sur son temps. Donc des délais honnêtes,
pas des délais de SLA :

- **accusé de réception sous 7 jours** ;
- une première évaluation (c'est une faille, ou ce n'en est pas une, et
  pourquoi) **sous 30 jours** ;
- un correctif publié dès qu'il est prêt, puis l'avis de sécurité rendu public
  avec ton crédit si tu le veux.

Sans réponse au bout de 30 jours, considère que le signalement n'est pas arrivé
et relance.

## Ce qui est dans le périmètre

Le code de ce dépôt : backend FastAPI, frontend, hooks du SDK, migrations,
images Docker et exemples de configuration fournis. En particulier :

- contournement de la porte de validation humaine (`git commit`, `git push`,
  `gh pr`, `glab mr` refusés au niveau du hook `PreToolUse`) par une session
  dont la publication n'a PAS été autorisée. Qu'un jeton d'agent l'autorise
  est voulu, cf. hors périmètre ;
- le push forcé (`--force`, `--mirror`, `-f`) accepté, y compris sur une
  session dont la publication est autorisée ;
- lecture ou écriture dans les projets, sessions ou prompts d'un autre
  utilisateur ;
- fuite d'un secret dans une réponse d'API, un journal ou le flux d'events :
  jeton Git, identifiants Claude, jeton d'agent, clé de chiffrement ;
- jeton accepté après révocation, ou jeton d'une porte accepté par une autre ;
- exécution de code hors du worktree d'une session, ou évasion de conteneur.

## Ce qui est hors périmètre

Ce ne sont pas des failles, c'est la conception. Elles sont documentées :

- **une session Claude tourne en `bypassPermissions`** : il n'y a pas de
  terminal côté serveur pour approuver une action. C'est la porte de validation
  humaine qui borne ce qui sort, pas le mode des permissions
  (`docs/sessions.md`) ;
- **un jeton d'agent extérieur donne les cinq outils ou rien**, et il vit dix
  ans : la borne est la révocation, pas l'expiration. Il n'existe pas
  d'autorisation fine par outil (`docs/agent-externe.md`) ;
- **un jeton d'agent extérieur peut ouvrir la publication**, donc publier sur
  les dépôts de son utilisateur. `allow_publish` est servi sur `/api/mcp/`
  depuis le 2026-10-30 : c'est une décision du mainteneur, prise pour avoir un
  agent autonome de bout en bout, et le risque d'injection de prompt par le
  texte des comptes rendus est assumé et documenté
  (`docs/securite-sessions.md`, garde nº2). Deux bornes restent mécaniques et
  sont, elles, dans le périmètre : un jeton n'ouvre que les sessions de SON
  utilisateur, et le push forcé reste refusé même porte ouverte ;
- **aucun plafond de dépense autonome** : la politique est d'alerter, jamais de
  bloquer ;
- **Eldir ne fournit pas de TLS** et n'a pas vocation à être exposé nu sur
  Internet. Il est pensé pour vivre derrière un reverse proxy ou un réseau
  privé ; une instance publiée sans jeton ni proxy n'est pas une faille
  (`docs/deployment.md`) ;
- ce qui est déjà écrit dans « Ce qui n'est pas garanti » de
  `docs/agent-externe.md` ;
- une vulnérabilité d'une dépendance déjà publiée en amont : signale-la en
  amont, et ouvre une issue ordinaire ici pour la montée de version ;
- les rapports de scanner automatique sans scénario d'exploitation.

## Versions suivies

La branche `main` uniquement. Eldir n'a pas encore de version taguée, donc pas
de correctif rétroporté : la mise à jour est un `git pull`.
