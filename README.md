# Audiovisuel du Collège de France

Page statique présentant les dernières parutions audio et vidéo du
[Collège de France](https://www.college-de-france.fr/fr/audios-videos),
navigables par thème : le [flux RSS officiel](https://www.college-de-france.fr/fr/audio-video-rss.xml)
des séances, plus les dernières vidéos des
[8 chaînes YouTube](https://www.college-de-france.fr/fr/le-college/diffusion-numerique-des-savoirs) du Collège.

`build.py` (Python 3, stdlib uniquement) relit le flux et les chaînes, télécharge
les vignettes (embarquées en data URI), classe chaque série dans son domaine via
la taxonomie des chaires du site et écrit :

- `index.html` — page complète, déployée sur GitHub Pages ;
- `cdf.html` — le même contenu en fragment, pour l'artifact claude.ai.

Le workflow [`deploy.yml`](.github/workflows/deploy.yml) reconstruit et déploie
le site chaque matin (cron 06:30 UTC), à chaque push, ou à la demande.

```bash
python3 build.py
```
