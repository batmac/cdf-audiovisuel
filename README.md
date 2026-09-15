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
le site trois fois par jour (cron 06:23, 12:41 et 18:07 UTC), à chaque push, ou
à la demande. Les sources tombent régulièrement (site du Collège en
maintenance ou en 502/504, YouTube en 404 depuis certains runners) :
`build.py` abandonne alors sans rien écrire, avec le code de sortie 75
(`EX_TEMPFAIL`). On ne déploie jamais une page dégradée, la version précédente
reste en ligne, et le workflow compte ce cas comme réussi (avec un
avertissement, pas d'alerte). Il n'échoue que sur un vrai bug de build, ou si
la page en ligne date de plus de `MAX_STALE_DAYS` jours (7) sans qu'aucune
reconstruction n'ait abouti ; ce second contrôle n'est bloquant qu'au créneau
du matin, pour ne pas recevoir plus d'un mail par jour pendant une panne longue.

```bash
python3 build.py
```
