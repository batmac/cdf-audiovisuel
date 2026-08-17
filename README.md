# Audiovisuel du Collège de France

Page statique présentant les dernières parutions audio et vidéo du
[Collège de France](https://www.college-de-france.fr/fr/audios-videos),
générée depuis le [flux RSS officiel](https://www.college-de-france.fr/fr/audio-video-rss.xml).

`build.py` (Python 3, stdlib uniquement) relit le flux, télécharge les vignettes
(embarquées en data URI), résout les titres de séries depuis le site et écrit :

- `index.html` — page complète, déployée sur GitHub Pages ;
- `cdf.html` — le même contenu en fragment, pour l'artifact claude.ai.

Le workflow [`deploy.yml`](.github/workflows/deploy.yml) reconstruit et déploie
le site chaque matin (cron 06:30 UTC), à chaque push, ou à la demande.

```bash
python3 build.py
```
