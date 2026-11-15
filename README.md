# Calendrier cyclocross élite 2026-27 (.ics dynamique)

Ce script Python tourne sur un Raspberry Pi. Il génère un fichier `.ics` avec toutes les courses élite de la saison : Coupe du Monde, Superprestige, X²O Trofee, HG Cross, championnats de Belgique et des Pays-Bas, Europe et Monde.

- **Un événement par course et par catégorie :** Femmes et Hommes. Chaque événement contient le nom, le lieu et l'heure de départ.
- **Vérification quotidienne de la startlist :** le script lit les courses des 7 prochains jours sur ProCyclingStats. Il écrit dans les notes le **top 10 des partants, trié par classement UCI**.
- **Heure officielle :** si PCS publie l'heure de départ, elle remplace l'heure estimée.
- **Publication sur GitHub :** le fichier est poussé sur GitHub, et Google Calendar s'y abonne par URL.

Seule la bibliothèque standard de Python 3.10 ou plus récent est utilisée. Raspberry Pi OS Bookworm fournit Python 3.11.

## Fichiers

| Fichier | Rôle |
|---|---|
| `cxcal.py` | Le script |
| `races.json` | Le calendrier de la saison (dates, lieux, heures locales), modifiable à la main |
| `config.json` | Les réglages : top N, fenêtre de vérification, URL PCS, push git |
| `cache/state.json` | Les startlists et heures déjà trouvées (créé automatiquement) |
| `docs/cyclocross-elite.ics` | Le calendrier généré |

## Installation

### 1. Créer le dépôt GitHub

1. Crée un dépôt **public**, par exemple `cx-calendar`. Google Calendar ne lit pas les URL privées.
2. Dans *Settings → Pages*, choisis *Deploy from a branch*, puis la branche `main` et le dossier `/docs`.

### 2. Installer sur le Raspberry Pi

```bash
git clone git@github.com:<ton-user>/cx-calendar.git ~/cx-calendar
# copie les fichiers de ce dossier dans ~/cx-calendar, puis :
cd ~/cx-calendar
python3 cxcal.py --all        # premier passage : toutes les courses
git add -A && git commit -m "Initial calendar" && git push
```

Le Raspberry Pi doit pouvoir pousser sans mot de passe. Utilise une clé SSH ajoutée sur GitHub, de préférence une *deploy key* avec droit d'écriture sur ce dépôt.

### 3. Lancer le script chaque jour (cron)

Tape `crontab -e` et ajoute :

```cron
# Chaque jour à 7h et 19h : met à jour les startlists et pousse le .ics
0 7,19 * * * cd $HOME/cx-calendar && /usr/bin/python3 cxcal.py >> cxcal.log 2>&1
```

### 4. S'abonner dans Google Calendar

1. Ouvre Google Calendar sur ordinateur, puis va dans *Autres agendas → + → À partir de l'URL*.
2. Colle l'URL `https://<ton-user>.github.io/cx-calendar/cyclocross-elite.ics`.
3. Valide. Le calendrier « Cyclocross Élite 2026-27 » apparaît.

> ⚠️ Google Calendar relit les agendas abonnés à son propre rythme, en général toutes les 12 à 24 h, et on ne peut pas le forcer. Une startlist publiée le matin peut donc apparaître sur ton téléphone seulement le soir ou le lendemain. Apple Calendar et Thunderbird respectent mieux l'intervalle de 6 h indiqué dans le fichier.

## Utilisation

```bash
python3 cxcal.py              # vérifie les courses de J-1 à J+7, régénère et pousse
python3 cxcal.py --all        # vérifie toutes les courses de la saison
python3 cxcal.py --no-fetch   # régénère le .ics depuis le cache, sans réseau
python3 cxcal.py --check      # affiche le slug PCS trouvé pour chaque course
```

## Le premier passage : vérifier la correspondance avec PCS

Le script retrouve seul chaque course sur ProCyclingStats. Il lit les calendriers `races.php` de PCS et compare le nom de la ville. Lance `--check` une fois. Pour chaque course marquée `??` ou associée à une mauvaise course :

1. Ouvre la course sur `cx.procyclingstats.com`.
2. Copie le slug de l'URL, par exemple `race/<slug>/2027/me`.
3. Ajoute-le dans `races.json` :

```json
{"id": "wc-tabor", ..., "pcs": {"me": "<slug>", "we": "<slug>"}}
```

Si l'URL du classement UCI femmes n'est pas la bonne, corrige `ranking_urls.we` dans `config.json`. En attendant, le script classe les partantes dans l'ordre des dossards, qui suit le classement UCI en cyclocross, et le précise dans la note.

## Heures

- Les heures de `races.json` sont des **heures locales** de chaque course. Le fichier `.ics` les stocke en UTC, et Google les affiche dans ton fuseau.
- Les heures non confirmées sont marquées « heure estimée, à confirmer » dans la note. Elles sont remplacées dès que PCS publie l'heure officielle. Tu peux aussi les corriger dans `races.json` et ajouter `"time_confirmed": true`.

## Limites

- Le script dépend de la structure HTML de ProCyclingStats. Si PCS change son site, la lecture peut casser. Les événements restent alors en place, sans startlist. Regarde `cxcal.log` en cas de doute.
- Les startlists paraissent en général quelques jours avant la course. Avant cela, la note indique « Startlist pas encore publiée ».
