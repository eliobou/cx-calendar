# Génération du calendrier

| Fichier | Rôle |
|---|---|
| `races.json` | La liste des courses, à modifier à la main |
| `cxcal.py` | Lit `races.json` et écrit `../cyclocross-elite.ics` |
| `../cyclocross-elite.ics` | Le calendrier publié par GitHub Pages (racine de `main`) |

## Modifier le calendrier

1. Modifie `races.json`.
2. Régénère le calendrier (Python 3.9+, rien à installer) :
   ```bash
   python3 script/cxcal.py
   ```
3. Commite et pousse `script/races.json` et `cyclocross-elite.ics`. Les agendas abonnés récupèrent la nouvelle version à leur prochaine actualisation.

## Format d'une course dans `races.json`

```json
{"id": "wc-namur", "name": "Coupe du Monde Namur", "series": "Coupe du Monde",
 "location": "Namur (Citadelle), Belgique", "tz": "Europe/Brussels",
 "date": "2026-12-27", "we_time": "13:30", "me_time": "15:00"}
```

| Champ | Description |
|---|---|
| `id` | Identifiant unique. **Ne pas le changer** : il sert d'UID à l'événement, et le changer crée un doublon dans les agendas |
| `name`, `series`, `location` | Textes affichés |
| `tz` | Fuseau horaire du lieu (`Europe/Brussels`, `Europe/Paris`…) |
| `date` | Jour de course (`AAAA-MM-JJ`) |
| `we_date`, `me_date` | Remplacent `date` quand Femmes et Hommes courent des jours différents |
| `we_time`, `me_time` | Heures de départ **locales** (`HH:MM`), Femmes / Hommes |
| `time_confirmed` | `true` si les heures sont officielles : retire la mention « heure estimée » |

Pour supprimer une course, retire-la de `races.json` : elle disparaît des agendas abonnés.

## Détails

- Les dates ont été vérifiées avec le calendrier de ProCyclingStats (novembre 2026).
- Les heures sont stockées en UTC dans le `.ics`. Chaque agenda les convertit dans le fuseau de l'utilisateur.
- Le `DTSTAMP` de chaque événement est calculé à partir de son contenu : relancer le script sans rien modifier produit exactement le même fichier.
