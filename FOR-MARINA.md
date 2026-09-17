# Pour Marina — votre mémoire permanente dans Claude

Ce dossier installe une **mémoire** que Claude garde entre les sessions. Vos
notes restent des fichiers Markdown, sur votre ordinateur. Rien n'est envoyé
sur Internet. Rien n'est payant à l'usage.

## Première installation (une seule fois, ~3 minutes)

**Sur Windows (le plus simple, sans taper de commandes) :**

1. Téléchargez le dossier (bouton vert **Code** → **Download ZIP** sur GitHub),
   puis décompressez-le.
2. **Double-cliquez sur « Install Marina Memory.bat »**.
3. Attendez 2 à 5 minutes. La fenêtre affiche la progression et reste ouverte à
   la fin.
4. **Quittez Claude complètement** : clic droit sur l'icône Claude près de
   l'horloge (zone de notification), puis **Quit**. Fermer la fenêtre ne suffit
   pas, la configuration ne serait pas rechargée.
5. Copiez les instructions de `CLAUDE-INSTRUCTIONS.md` dans
   **Réglages → Profil → Instructions personnalisées** de Claude.

Rien n'est à installer avant : si `uv` manque, le script le récupère, et `uv`
récupère Python lui-même. Sur un PC d'école ou d'entreprise où PowerShell est
bloqué, le script affiche la commande à lancer manuellement au lieu d'échouer.

**Sur Mac :** mêmes étapes avec « Install Marina Memory.command », mais
**clic droit → Ouvrir** la première fois, et quittez Claude avec **Cmd+Q**.

**Ou en ligne de commande :**

```bash
git clone https://github.com/ffouladgar-ux/marina-memory.git
cd marina-memory && ./install.sh
```

Si `git clone` demande un mot de passe, l'invitation GitHub n'est pas encore
acceptée : vérifiez votre e-mail.

Pour vérifier à tout moment : `mm doctor`.

## Pourquoi c'est moins cher à utiliser

Le problème habituel : on colle un document entier dans la conversation, et il
est repayé à chaque message. Ici, quatre mécanismes :

1. **Deux étages.** Seul `index.md` (~900 tokens, une liste de pointeurs)
   occupe le contexte. Le reste est lu à la demande.
2. **Les documents sont convertis une fois.** PDF, DOCX, PPTX → Markdown
   localement (90–95 % plus léger), stockés, puis lus par sections. Jamais
   recollés dans la conversation.
3. **Lectures sectionnées.** Claude peut demander seulement les passages qui
   répondent à la question.
4. **Aucun appel payant pour mémoriser.** La recherche est locale (SQLite). Vous
   pouvez accumuler autant de mémoire que vous voulez, cela ne coûte rien.

## Les 3 règles

1. **Ne collez jamais un document.** Enregistrez le fichier, puis dites :
   *« ingère ~/Downloads/chapitre3.pdf »*. Claude le convertit, le range, et le
   relit par sections ensuite.
2. **Ne réexpliquez jamais deux fois.** Si Claude redemande quelque chose que
   vous avez déjà dit, dites-le : c'est un bug d'habitude, pas votre mémoire.
3. **Laissez-le ranger.** Les domaines sont choisis automatiquement (`business`,
   `studies`, `people`, `personal`, `health`, `inbox`). Rien n'est perdu : ce qui
   est incertain va dans `inbox`, et se reclasse en une phrase.

## Commandes utiles

```bash
mm recall                       # affiche l'index (ce que Claude sait)
mm recall "examen de mémoire"   # cherche
mm remember "..."               # mémorise une info
mm ingest ~/Downloads/x.pdf     # range un document
mm open slug -q "question"      # relit un document, passages utiles seulement
mm status                       # combien de souvenirs, où
mm doctor                       # vérifie que tout va bien
```

## Où sont vos fichiers

```
~/MemoryVault/
├── index.md          l'index (automatique)
├── studies/          école de journalisme : cours, échéances, mémoires
├── business/         clients, factures, tarifs, pitchs
├── people/           qui est qui, contacts, anniversaires
├── personal/         logement, admin, voyage, assurances
├── health/           rendez-vous, symptômes, sommeil, concentration
├── inbox/            à reclasser
├── sources/          vos documents, en Markdown
└── _archive/         ce qui a été « oublié » — conservé, jamais détruit
```

Ouvrez ce dossier dans Obsidian si vous voulez le lire confortablement : ce
sont des fichiers Markdown, Obsidian les affiche tels quels.

**Les fichiers Markdown sont la mémoire.** La base de données n'est qu'un
index jetable : supprimez-la, `mm reindex` la reconstruit à partir des
fichiers.

## Sauvegarde (optionnel, recommandé)

```bash
cd ~/MemoryVault && git init && git add . && git commit -m "ma mémoire"
```
Puis, si vous le souhaitez, poussez vers un dépôt **privé**.

## Limites, dites franchement

- La recherche est lexicale (mots exacts, noms propres, dates), pas sémantique.
  « épuisée » ne retrouvera pas une note qui dit seulement « burnout ».
- Les PDF uniquement scannés et l'audio demandent les extras :
  `pip install 'marina-memory[extras]'`.

---

# For Marina — your permanent memory in Claude

Short English version of the same pages.

**What it is:** a memory Claude keeps between sessions. Your notes are plain
Markdown files on your own machine. Nothing is uploaded, nothing costs money at
runtime.

**Three rules**
1. Never paste a document — save it and say *"ingest ~/Downloads/chapter3.pdf"*.
2. Never re-explain something you've already told it.
3. Let it file things itself; anything unclear lands in `inbox`, never lost.

**Commands:** `mm recall` (show what it knows) · `mm remember "..."` ·
`mm ingest FILE` · `mm open SLUG -q "question"` · `mm status` · `mm doctor`

**Compartments:** `studies`, `business`, `people`, `personal`, `health`,
`inbox`, `sources`.

**Honest limits:** search is lexical (exact terms, names, dates), not semantic.
Scanned PDFs and audio need `pip install 'marina-memory[extras]'`.
