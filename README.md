# Audiovisuel du Collège de France

Page statique présentant les dernières parutions audio et vidéo du
[Collège de France](https://www.college-de-france.fr/fr/audios-videos),
navigables par thème : le [flux RSS officiel](https://www.college-de-france.fr/fr/audio-video-rss.xml)
des séances, plus les dernières vidéos des
[8 chaînes YouTube](https://www.college-de-france.fr/fr/le-college/diffusion-numerique-des-savoirs) du Collège.

La page est un fil unique de cartes par thème, trié par date décroissante, avec
un badge de provenance. Les chaînes YouTube thématiques republient les séances du
site sous des titres génériques : ces doublons sont écartés au profit des fiches
du site, plus riches.

`build.py` (Python 3, stdlib uniquement) relit le flux et les chaînes, télécharge
les vignettes (embarquées en data URI), classe chaque série dans son domaine via
la taxonomie des chaires du site et écrit :

- `index.html` — page complète, déployée sur GitHub Pages ;
- `cdf.html` — le même contenu en fragment, pour l'artifact claude.ai.

Le workflow [`deploy.yml`](.github/workflows/deploy.yml) reconstruit et déploie
le site chaque matin (cron 06:30 UTC, seconde chance à 12:30), à chaque push, ou
à la demande. YouTube répondant parfois 404 depuis les runners, `build.py`
échoue volontairement dès qu'une source manque : on ne déploie jamais une page
dégradée, la version précédente reste en ligne.

```bash
python3 build.py
```
