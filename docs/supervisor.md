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

## Eldir apprend tes habitudes

Quand tu exprimes une préférence durable ("sur ce projet, toujours une PR",
"nomme les branches comme ça"), le superviseur appelle son outil `remember` et la
ligne est ajoutée au prompt **Préférences apprises par le superviseur**.

C'est un simple prompt système : tu le lis, le corriges ou le vides dans
**Settings > Prompts**. Rien n'est appris dans ton dos, rien n'est stocké ailleurs.
Une préférence enregistrée est prise en compte au démarrage suivant du superviseur.

## Ses quatre outils

| Outil | Ce qu'il fait |
|---|---|
| `list_projects` | Les repos branchés sur Eldir, pour identifier de quel projet tu parles |
| `list_sessions` | Les sessions existantes, leur état et leur dernier compte rendu |
| `dispatch` | Transmet une consigne à une session (reprise ou créée), sans attendre |
| `remember` | Enregistre une préférence de travail durable |

Il n'a **aucun** autre outil : ni `Bash`, ni `Read`, ni `Write`, ni accès réseau.
Ce n'est pas une consigne de prompt mais une restriction du SDK (`disallowed_tools`).

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
- **Pas de parallélisme sur un même repo** : `dispatch` reprend la session la plus
  récente du projet. Pour deux chantiers en parallèle sur le même repo, crée la
  seconde session à la main depuis la page Ops et donne son id au superviseur.
- **Préférences appliquées au redémarrage** : le prompt du superviseur est
  reconstruit quand sa session redémarre, pas en cours de conversation.
