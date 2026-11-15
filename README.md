# Calendrier cyclocross élite 2026-27 (.ics)

Ce script Python génère un fichier `.ics` avec toutes les courses élite de la saison de cyclocross 2026-27 : Coupe du Monde, Superprestige, X²O Trofee, HG Cross, championnats de Belgique, des Pays-Bas, d'Europe et du Monde. Le fichier est publié sur GitHub Pages et Google Calendar (ou tout autre agenda) s'y abonne par URL.

Seule la bibliothèque standard de Python est utilisée (Python **3.9 ou plus récent**). Raspberry Pi OS Bookworm fournit Python 3.11.

## État actuel du projet

| Fonction | État |
|---|---|
| Calendrier des 39 courses (78 événements : Femmes et Hommes) | ✅ Fonctionne |
| Heures de départ converties en UTC, affichées dans le fuseau de l'agenda | ✅ Fonctionne |
| Fichier `.ics` conforme RFC 5545 (vérifié avec la bibliothèque `icalendar`) | ✅ Fonctionne |
| Publication automatique sur GitHub (`git_push`) | ⏸️ Désactivée tant que le dépôt distant n'est pas créé |
| Top 10 de la startlist et heure officielle depuis ProCyclingStats | ⛔ **Désactivé** : PCS bloque les accès automatisés (voir [Limites](#limites-et-solutions-possibles)) |

Chaque événement contient aujourd'hui : la série, la catégorie, l'heure de départ (heure de Paris, avec la mention « heure estimée, à confirmer » si elle n'est pas confirmée) et le lieu.

## Fichiers

| Fichier | Rôle | Versionné |
|---|---|---|
| `cxcal.py` | Le script | oui |
| `races.json` | Le calendrier de la saison (dates, lieux, heures locales), modifiable à la main | oui |
| `config.json` | Les réglages (voir [Configuration](#configuration)) | oui |
| `docs/cyclocross-elite.ics` | Le calendrier généré, servi par GitHub Pages | oui |
| `cache/state.json` | État local : numéros de version des événements, startlists et heures trouvées (créé automatiquement) | non (`.gitignore`) |
| `cache/pcs_races.json` | Liste des courses PCS, gardée 7 jours (uniquement si les startlists sont activées) | non (`.gitignore`) |
| `cxcal.log` | Journal du cron, si tu rediriges la sortie vers ce fichier | non (`.gitignore`) |

## Utilisation

```bash
python3 cxcal.py              # régénère le .ics (et vérifie les startlists si activé)
python3 cxcal.py --no-fetch   # régénère le .ics depuis races.json et le cache, sans réseau
python3 cxcal.py --all        # (startlists activées) vérifie toutes les courses de la saison
python3 cxcal.py --check      # (startlists activées) affiche le slug PCS trouvé pour chaque course
```

Options pour les tests :

| Option | Effet |
|---|---|
| `--today AAAA-MM-JJ` | Simule une autre date du jour (fenêtre de vérification des startlists) |
| `--offline DOSSIER` | Lit des pages HTML locales au lieu d'interroger PCS (voir [Tester](#tester-sans-réseau)) |
| `--config FICHIER` | Utilise un autre fichier de configuration |
| `--races FICHIER` | Utilise un autre calendrier |

Après une modification de `races.json` :

```bash
python3 cxcal.py
git add -A && git commit -m "Mise à jour du calendrier" && git push
```

## Installation

### 1. Créer le dépôt GitHub

1. Crée un dépôt **public**, par exemple `cx-calendar`. Google Calendar ne lit pas les URL privées.
2. Relie le dépôt local et pousse :
   ```bash
   git remote add origin git@github.com:<ton-user>/cx-calendar.git
   git push -u origin main
   ```
3. Dans *Settings → Pages*, choisis *Deploy from a branch*, puis la branche `main` et le dossier `/docs`.
4. Vérifie que `https://<ton-user>.github.io/cx-calendar/cyclocross-elite.ics` se télécharge.

### 2. S'abonner dans Google Calendar

1. Ouvre Google Calendar sur ordinateur, puis va dans *Autres agendas → + → À partir de l'URL*.
2. Colle l'URL `https://<ton-user>.github.io/cx-calendar/cyclocross-elite.ics`.
3. Valide. Le calendrier « Cyclocross Élite 2026-27 » apparaît, et se synchronise ensuite sur le téléphone.

Apple Calendar : *Fichier → Nouvel abonnement à un calendrier*, même URL.

### 3. (Optionnel) Automatiser sur un Raspberry Pi

**Sans les startlists, le Pi n'est pas nécessaire** : le `.ics` ne change que lorsque `races.json` change. Il suffit de lancer le script et de pousser depuis n'importe quel ordinateur après chaque modification.

Le Pi devient utile si les startlists sont réactivées (mise à jour quotidienne). Dans ce cas :

```bash
git clone git@github.com:<ton-user>/cx-calendar.git ~/cx-calendar
cd ~/cx-calendar
python3 cxcal.py --all
```

Mets `"git_push": true` dans `config.json`. Le Pi doit pouvoir pousser sans mot de passe : utilise une clé SSH, de préférence une *deploy key* avec droit d'écriture sur ce dépôt.

Puis `crontab -e` :

```cron
# Chaque jour à 7h et 19h : met à jour les startlists et pousse le .ics
0 7,19 * * * cd $HOME/cx-calendar && /usr/bin/python3 cxcal.py >> cxcal.log 2>&1
```

⚠️ Si tu modifies aussi `races.json` depuis un autre ordinateur, fais `git pull` sur le Pi avant, sinon le push du Pi échouera (voir [Limites](#limites-et-solutions-possibles)).

## Configuration

`config.json` surcharge les valeurs par défaut définies dans `cxcal.py` (`DEFAULT_CONFIG`). Une clé absente reprend la valeur par défaut.

| Clé | Valeur actuelle | Rôle |
|---|---|---|
| `output` | `docs/cyclocross-elite.ics` | Chemin du fichier généré, relatif à `git_repo` |
| `calendar_name` | `Cyclocross Élite 2026-27` | Nom affiché dans l'agenda (`X-WR-CALNAME`) |
| `event_duration_minutes` | `60` | Durée de chaque événement |
| `fetch_startlists` | `false` | Active la lecture des startlists et des heures sur PCS |
| `top_n` | `10` | Nombre de coureurs listés dans la note |
| `lookahead_days` | `7` | Fenêtre de vérification : de J-1 à J+N |
| `request_delay_seconds` | `2.0` | Pause entre deux requêtes vers PCS |
| `pcs_base` | `https://cx.procyclingstats.com` | Adresse du site PCS cyclocross |
| `pcs_years` | `[2026, 2027]` | Années PCS dans lesquelles chercher les courses |
| `ranking_urls` | voir le fichier | Pages du classement UCI hommes (`me`) et femmes (`we`) ; plusieurs URL possibles, la première qui donne au moins 20 coureurs est retenue |
| `git_push` | `false` | Après génération : `git add` du `.ics`, commit et push |
| `git_repo` | `.` | Dossier du dépôt git |

## Format de `races.json`

```json
{"id": "wc-tabor", "name": "Coupe du Monde Tábor", "series": "Coupe du Monde",
 "location": "Tábor, Tchéquie", "tz": "Europe/Prague",
 "date": "2026-11-29", "we_time": "13:30", "me_time": "15:00"}
```

| Champ | Obligatoire | Rôle |
|---|---|---|
| `id` | oui | Identifiant unique et stable. Il sert d'UID dans le `.ics` (`<id>-we@cxcal`, `<id>-me@cxcal`) : **ne le change pas** en cours de saison, sinon l'agenda verra un nouvel événement au lieu d'une mise à jour |
| `name` | oui | Titre de l'événement (suivi de « – Femmes » ou « – Hommes ») |
| `series` | oui | Série, affichée dans la note et dans `CATEGORIES` |
| `location` | oui | Lieu affiché. La partie avant la première virgule ou parenthèse sert aussi à retrouver la course sur PCS |
| `tz` | oui | Fuseau IANA du lieu de la course (`Europe/Brussels`, `Europe/London`…) |
| `date` | oui, sauf si `we_date` et `me_date` | Date commune aux deux courses |
| `we_date`, `me_date` | non | Dates séparées Femmes / Hommes (championnats sur deux jours) |
| `we_time`, `me_time` | oui | Heures de départ **locales** (`HH:MM`) |
| `time_confirmed` | non | `true` si les heures sont officielles : retire la mention « heure estimée » |
| `pcs` | non | Force le slug PCS : `{"me": "<slug>", "we": "<slug>"}` |

Le script ne valide pas ce fichier : un champ manquant ou une date mal écrite fait planter la génération. Lance `python3 cxcal.py --no-fetch` après chaque modification pour vérifier.

## Heures

- Les heures de `races.json` sont des **heures locales**. Le `.ics` les stocke en UTC ; l'agenda les affiche dans ton fuseau. La note indique l'heure de Paris.
- Sauf pour la Bollekescross (Hamme-Zogge), les heures sont **estimées** à partir des horaires habituels : 13h30 / 15h00 pour la plupart des courses, avec des exceptions pour les nocturnes, les championnats et la Coupe du Monde. Elles sont marquées « heure estimée, à confirmer ».
- Pour corriger une heure : modifie `we_time` / `me_time`, ajoute `"time_confirmed": true`, régénère et pousse.
- Les heures publiées par les organisateurs (souvent sur leur site ou dans le guide de course) sont la source la plus fiable.

## Comment l'agenda reçoit les mises à jour

- Chaque événement a un UID fixe et un numéro `SEQUENCE`. Quand l'heure ou la note d'un événement change, le script augmente `SEQUENCE` et met à jour `LAST-MODIFIED`. Ces numéros sont gardés dans `cache/state.json`.
- Le fichier annonce un intervalle de rafraîchissement de 6 h (`REFRESH-INTERVAL`, `X-PUBLISHED-TTL`).
- ⚠️ **Google Calendar ignore cet intervalle** : il relit les agendas abonnés à son propre rythme, en général toutes les 12 à 24 h, parfois plus, et on ne peut pas le forcer. Apple Calendar et Thunderbird respectent mieux l'intervalle de 6 h.

## Fonction startlist (désactivée)

Le code est toujours présent et testé hors ligne. Quand `fetch_startlists` vaut `true`, à chaque lancement :

1. Le script sélectionne les courses de J-1 à J+`lookahead_days`.
2. Il charge le classement UCI hommes et femmes sur PCS.
3. Il retrouve la course sur PCS : slug forcé (`pcs` dans `races.json`), sinon slug déjà trouvé (cache), sinon recherche dans les calendriers `races.php` de PCS en comparant le nom de la ville.
4. Il lit la startlist, trie les partants par classement UCI (ou par ordre des dossards si le classement est indisponible) et écrit le top N dans la note, avec le lien vers la startlist et la date de la dernière vérification.
5. Si PCS publie l'heure de départ, elle remplace l'heure estimée.

Pour la réactiver : `"fetch_startlists": true` dans `config.json`, puis `python3 cxcal.py --check` pour vérifier les correspondances de slugs. **Ne la réactive pas avant d'avoir résolu le point 1 ci-dessous**, sinon toutes les vérifications échoueront.

## Limites et solutions possibles

### 1. ProCyclingStats bloque le script (bloquant pour les startlists)

**Constat (15/11/2026)** : toutes les pages PCS répondent `HTTP 403` avec l'en-tête `cf-mitigated: challenge`. C'est une vérification anti-robot Cloudflare qui exige l'exécution de JavaScript dans un navigateur. `urllib` ne peut pas la passer, quelle que soit la machine (Mac ou Pi). Le script ne récupère donc ni startlist, ni classement, ni heure officielle.

Contourner ce blocage (faux navigateur, navigateur automatisé, service anti-Cloudflare) va contre la volonté explicite du site et peut enfreindre ses conditions d'utilisation : ce n'est pas une piste retenue.

**Solutions possibles :**
- **Une autre source qui accepte les accès automatisés** : sites des organisateurs (Superprestige, X²O Trofee, HG Cross, UCI), qui publient startlists et horaires ; ou une API ou un flux public de résultats. Il faut écrire un analyseur par source.
- **Demander l'accès à PCS** : PCS propose parfois un accès pour les usages personnels ou une API ; à demander directement.
- **Saisie manuelle** : ajouter dans `races.json` un champ (par exemple `"top": {"me": [...], "we": [...]}`) que le script écrirait dans la note. Simple et fiable, mais demande quelques minutes par week-end.
- **Garder seulement le calendrier fixe** : c'est l'état actuel, il fonctionne déjà bien.

### 2. Risque de prendre la startlist de la saison précédente

`season_years()` essaie deux années PCS (2026 et 2027). Selon la façon dont PCS numérote les saisons de cyclocross, l'une des deux désigne l'édition de l'an dernier, dont la startlist existe déjà. Si celle de cette saison n'est pas encore publiée, le script prend l'ancienne sans le signaler.

**Solution** : déterminer une fois la convention de PCS (année civile ou année de fin de saison) et n'essayer qu'une année, ou vérifier que la date affichée sur la page correspond à la date de la course.

### 3. Recherche automatique des courses PCS peu fiable

La recherche compare le nom de la ville en français (`location`) au slug PCS, avec une simple recherche de sous-chaîne. Tests effectués :
- « Anvers », « Bruxelles », « Kelvingrove Park » (Glasgow) et « Hamme-Zogge » ne trouvent rien : PCS utilise les noms locaux ou anglais (Antwerpen, Brussel…), et le premier élément de `location` n'est pas toujours la ville.
- « Mol » trouve aussi « molenbeek », classé en premier.
- Hamme : la Coupe du Monde et la Bollekescross peuvent être confondues.

**Solutions** : renseigner `"pcs": {...}` pour chaque course (le plus sûr) ; ou ajouter un champ `town` avec le nom local ; et comparer des mots entiers plutôt que des sous-chaînes.

### 4. Gestion des erreurs réseau incomplète

- Un blocage (403) est journalisé comme « fetch failed », puis la course est notée « startlist not published yet » : le message est trompeur.
- Seules `URLError` et `TimeoutError` sont rattrapées. Une connexion coupée en cours de lecture (`ConnectionResetError`, `http.client.IncompleteRead`) fait planter tout le script, et le `.ics` n'est pas régénéré.

**Solutions** : rattraper `OSError` et `http.client.HTTPException` ; détecter l'en-tête `cf-mitigated` ou le code 403 et l'écrire clairement dans le journal.

### 5. Commits inutiles (startlists activées)

La ligne « Dernière vérification » change à chaque passage. Le cron crée donc un commit et une nouvelle `SEQUENCE` deux fois par jour pour chaque course de la fenêtre, même si la startlist n'a pas changé.

**Solution** : exclure cette ligne du calcul de l'empreinte (`digest`) dans `build_event`, ou ne la mettre à jour que si la startlist change.

### 6. Push git fragile

`git_publish` lance `git push` sans `git pull --rebase` avant. Si le dépôt distant a reçu d'autres commits (modification de `races.json` depuis un autre ordinateur), le push échoue à chaque passage, en silence sauf dans le journal.

**Solution** : faire `git pull --rebase` avant de commiter ; ou ne modifier `races.json` que sur la machine qui pousse.

### 7. État local non sauvegardé

`cache/state.json` n'est pas versionné. S'il est perdu (nouvelle machine, nouveau clone), les numéros `SEQUENCE` repartent à 0. Les agendas l'acceptent en général, mais certains peuvent ignorer une mise à jour dont la `SEQUENCE` est plus basse.

**Solution** : versionner `state.json`, ou calculer `SEQUENCE` à partir d'un horodatage plutôt qu'un compteur.

### 8. Calendrier maintenu à la main

Les dates et lieux de `races.json` ont été saisis à la main pour la saison 2026-27. Un changement de date ou une annulation n'est pas détecté.

**Solution** : vérifier les calendriers officiels (UCI, organisateurs des séries) en début de saison et au fil de l'eau ; mettre à jour `races.json`, régénérer et pousser. Pour la saison suivante : nouveau `races.json`, nouveau `calendar_name`, et `pcs_years` à adapter.

### 9. Dépendance à la structure HTML de PCS

Même avec un accès autorisé, le script lit le HTML de PCS avec des expressions régulières. Si PCS change son site, la lecture casse : les événements restent en place, sans startlist. Regarde `cxcal.log` en cas de doute.

### 10. Délai de Google Calendar

Voir [Comment l'agenda reçoit les mises à jour](#comment-lagenda-reçoit-les-mises-à-jour) : jusqu'à 24 h, ou plus, entre un push et l'affichage dans Google Calendar. Aucune solution côté script ; Apple Calendar est plus réactif.

## Tester sans réseau

`--offline DOSSIER` remplace chaque requête par la lecture d'un fichier local. Le nom du fichier est l'URL passée dans `slugify` suivie de `.html`. Par exemple, `https://cx.procyclingstats.com/rankings/me/uci-ranking` devient `https-cx-procyclingstats-com-rankings-me-uci-ranking.html`.

```bash
python3 cxcal.py --offline fixtures/ --today 2026-11-15
```

Pour ne pas écraser le vrai cache et le vrai `.ics`, lance les tests dans une copie du dossier. Avec `--offline`, la mise à jour des startlists n'a lieu que si `fetch_startlists` vaut `true` ; `--check` l'utilise dans tous les cas.

## À faire

- [ ] Créer le dépôt GitHub public, activer Pages, pousser, s'abonner dans Google Calendar.
- [ ] Remettre `"git_push": true` si le script tourne en automatique.
- [ ] Choisir une solution pour les startlists (limite 1).
- [ ] Avant de réactiver les startlists : corriger les limites 2 à 6.
- [ ] Confirmer les heures de départ au fil de la saison (`time_confirmed`).
