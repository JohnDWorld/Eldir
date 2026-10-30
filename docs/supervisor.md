# Le superviseur Eldir

> Une seule conversation pour piloter toutes tes sessions Claude.

Au lieu d'ouvrir une session par repo et de jongler entre les onglets, tu parles à
**Eldir**, une session Claude qui n'a ni éditeur ni terminal : elle sait seulement
identifier tes projets, transmettre des consignes aux sessions qui travaillent
dessus, et te restituer ce qu'elles ont fait.

Onglet **Eldir** dans la barre du haut, ou `/supervisor`.

## La boucle complète

```
   toi ──"ajoute telle compétence à Munin"──► superviseur
                                                 │ list_projects → identifie Munin
                                                 │ list_sessions → une session est ouverte ?
                                                 ▼
                                            dispatch(consigne)
                                                 │
                                    session Munin (worktree isolé)
                                                 │ travaille, modifie des fichiers
                                                 │ termine son tour par un bloc <cr>
                                                 ▼
                                        <cr> → sessions.summary
                                                 │ (écrase le compte rendu précédent)
                                                 ▼
   toi ◄──"voilà ce qu'elle a fait"──── superviseur (réveillé automatiquement)
    │
    └─► tu relis le diff dans la session, puis Commit & Push ou Ouvrir une PR
```

Le superviseur n'attend pas la session enfant : `dispatch` lui rend la main tout de
suite. Tu peux continuer à lui parler pendant que la session travaille. Quand le
tour de l'enfant se termine, Eldir reçoit automatiquement le compte rendu et te
répond.

## Le compte rendu `<cr>`

Chaque session projet termine ses tours par un bloc court :

```
<cr>
FAIT: extraction du parser dans memory/parser.py
FICHIERS: munin/memory/parser.py, tests/test_parser.py
RESTE: rien
BLOCAGE: aucun
PRET: oui
</cr>
```

Ce bloc **écrase le précédent** : une session n'a qu'un seul compte rendu, celui de
son dernier passage. C'est ce qui garde la relecture du superviseur à coût constant,
qu'une session ait fait un tour ou cinquante. Il est stocké dans la colonne
`sessions.summary` et s'affiche dans la carte de session sur la page Ops.

La consigne qui impose ce format vit dans le prompt **Protocole session enfant**
(Settings > Prompts), éditable comme les autres.

## Chaîner deux repos sans faire le courrier

C'est le cas d'usage qui justifie le superviseur. Exemple réel :

```
toi ──► "Rempart Messenger change son protocole de messages, propage"
             │
             ├─► dispatch(Rempart Messenger, "…")
             │      └─ <cr> FAIT: nouveau champ `envelope.version` …
             │
             ├─► dispatch(Village Viking, "Rempart expose maintenant
             │      `envelope.version`, adapte le client …")
             │      └─ <cr> FAIT: client mis à jour, adaptateur …
             │
             └─► dispatch(Boutique à Agents, "Village Viking expose …")
                    └─ <cr> …
```

Le superviseur extrait du compte rendu de chaque session ce dont la suivante a
besoin (noms exacts, signatures, chemins) et le lui transmet lui-même. Tu ne
copies-colles plus rien entre deux conversations.

Il enchaîne **un maillon à la fois**, en attendant le compte rendu de chaque
session : une chaîne lancée sur une base fausse coûte trois sessions au lieu
d'une. Et il ne chaîne que sur une dépendance qu'il connaît, sinon il demande.

Pour rendre une dépendance durable, dis-la une fois : *"quand Rempart Messenger
change son protocole, Village Viking doit suivre"*. Le superviseur l'enregistre
via `remember` et l'appliquera sans que tu la répètes.

## Tu restes le seul à publier

Les sessions Claude tournent sans demande d'autorisation (pas de terminal côté
serveur), donc rien ne les empêcherait de pousser toutes seules. Eldir refuse au
niveau du hook `PreToolUse` toute commande `git commit`, `git push`, `gh pr` ou
`glab mr` : la tentative apparaît dans le flux d'events, et l'agent reçoit
l'explication à la place du résultat.

Les modifications restent donc non commitées dans le worktree de la session. Tu les
relis dans l'onglet **diff**, puis tu déclenches toi-même **Commit & Push** ou
**Ouvrir une PR**. Ces deux actions passent par le backend Eldir, pas par l'agent :
elles ne sont pas concernées par le refus.

Si tu veux qu'une session publie elle-même, tu lèves le refus pour elle seule, depuis
le dashboard ou en le demandant au superviseur (`allow_publish`). Le drapeau est
persistant : une session dormante le retrouve à son prochain démarrage, donc referme-le
quand le travail est relu. Même autorisée, une session ne peut pas réécrire
l'historique distant : `git push --force` reste refusé dans tous les cas.

## Eldir apprend tes habitudes

Quand tu exprimes une préférence durable ("sur ce projet, toujours une PR",
"nomme les branches comme ça"), le superviseur appelle son outil `remember` et la
ligne est ajoutée au prompt **Préférences apprises par le superviseur**.

C'est un simple prompt système : tu le lis, le corriges ou le vides dans
**Settings > Prompts**. Rien n'est appris dans ton dos, rien n'est stocké ailleurs.
Une préférence enregistrée est prise en compte au démarrage suivant du superviseur.

Un agent extérieur peut appeler le même outil, et ses lignes portent alors la marque
de son jeton (`- [agent « nom »] …`). Le superviseur les lit comme des suggestions, et
elles sont plafonnées. Tu les vois et tu en fais le ménage dans **Settings > Agents
extérieurs**. Voir [`docs/agent-externe.md`](./agent-externe.md).

## Ses cinq outils

| Outil | Ce qu'il fait |
|---|---|
| `list_projects` | Les repos branchés sur Eldir, avec pour chacun sa dernière activité et le nombre de sessions qui attendent un geste de ta part. Sert à identifier de quel projet tu parles, et à repérer ceux qui dorment |
| `list_sessions` | Les sessions existantes, leur état et leur dernier compte rendu |
| `dispatch` | Transmet une consigne à une session (reprise ou créée), sans attendre. Avec `nouveau_chantier`, ouvre une session neuve à côté des existantes plutôt que de reprendre la plus récente |
| `allow_publish` | Autorise une session à publier (commit, push, PR) ou lui retire ce droit. Le superviseur ne s'en sert que si tu le lui demandes explicitement : c'est ta porte, pas la sienne |
| `remember` | Enregistre une préférence de travail durable |

Il n'a **aucun** autre outil : ni `Bash`, ni `Read`, ni `Write`, ni accès réseau.
Ce n'est pas une consigne de prompt mais une restriction du SDK (`disallowed_tools`).

La **dernière activité** de `list_projects` est la dernière écriture sur la ligne de
session, pas la date du dernier commit : un projet dont une session a bougé hier est
« actif d'hier », quel que soit l'âge de son historique git.

Ces cinq outils sont aussi servis en MCP sur HTTP, pour qu'un agent extérieur puisse
piloter Eldir comme le fait cette conversation. Un seul corps par outil et une seule
table de descriptions : les deux transports ne peuvent pas diverger. Voir
[`docs/agent-externe.md`](./agent-externe.md), qui dit surtout ce qu'un jeton
d'agent accorde.

## Ce que ça coûte

Le superviseur est une session comme les autres : elle apparaît dans le dashboard,
ses tokens sont comptés dans `/costs` (marquée `is_system`). Son coût reste faible
parce qu'elle ne lit jamais de code : elle ne manipule que des noms de projets et
des comptes rendus de 10 lignes.

## Surveillance des repos

En parallèle, Eldir fetch et fast-forward les clones de tes projets toutes les
15 minutes (`REPO_SYNC_INTERVAL_MINUTES`, `0` pour désactiver). La règle est la
même que pour le bouton **sync** manuel : jamais de pull si le working tree est
sale ou si le clone n'est pas sur sa branche par défaut. Les worktrees des sessions
en cours ne sont jamais touchés.

## Limites connues

- **Mono-utilisateur** : un superviseur par utilisateur, comme le reste de la V1.
- **Préférences appliquées au redémarrage** : le prompt du superviseur est
  reconstruit quand sa session redémarre, pas en cours de conversation.
- **Les tours en cours vivent en mémoire** : si Eldir redémarre pendant qu'une
  session dispatchée travaille, le tour est interrompu et plus rien n'annonce sa fin.
  Il faut relancer la consigne, comme il faut reprendre la session elle-même.
