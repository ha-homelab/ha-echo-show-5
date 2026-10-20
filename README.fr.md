# Echo Show 5 Gen2 → Android → Home Assistant

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15595/badge)](https://www.bestpractices.dev/projects/15595)

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · **Français**

Ce projet transforme un **Amazon Echo Show 5 de deuxième génération (2021), nom de code `cronos`**, en satellite vocal Home Assistant, horloge lisible, écran de caméra sur détection de mouvement et terminal multimédia commandable à distance. Le dépôt fournit les outils de conversion accompagnée, les correctifs locaux, les intégrations et les procédures de récupération. Il ne contient ni firmware, ni APK, ni modèle d’activation privé, ni identifiants.

Commencez par le [wiki du projet](docs/wiki/Home.md). Pour un appareil d’origine, suivez le [guide de conversion](docs/runbook.md) ; pour un appareil déjà sous Android, utilisez le [guide de mise à jour et de récupération](docs/wiki/Installation-and-recovery.md). **Ne répétez pas le déverrouillage d’un appareil déjà déverrouillé.** Les guides techniques détaillés restent maintenus en anglais ; cette page est le point d’entrée en français.

![Architecture : le Show communique avec HA ; la voix, les caméras et les appels suivent des chemins distincts. Les légendes du diagramme sont en anglais.](docs/assets/architecture.svg)


[![Écran de l’horloge en perspective](docs/assets/clock-hero.png)](docs/assets/clock-screenshot.jpg)

La véritable page de l’horloge `20261015-r11`, capturée dans Chrome sur ordinateur
à 960 × 480 avec la configuration d’exemple. Sans connexion à Home Assistant,
caméra ni appareil. Cliquez pour voir l’original.

## 20 octobre : cycle du détecteur vérifié sur Show 1

**Show 1 utilise `myshka.9` / `7009` avec « Привет, мышка » et « Hey Jarvis ».**
Myshka conserve **0,50** ; Jarvis garde sa moyenne indépendante sur cinq
évaluations **> 0,97**. Un microphone alimente les deux phrases et la commande
Stop séparée. La mise à jour attend la fermeture de l’ancien détecteur et ne
démarre aucune capture quand la phrase principale est désactivée.
Si une étape de l’arrêt échoue, cette version exécute quand même les autres étapes de libération des ressources.

**62 tests JVM** et **six tests Android** ont réussi. Les changements de réglages
sans redémarrage, la désactivation de la phrase principale, **trois cycles réels
de coupure et reprise du microphone** et un redémarrage ont été vérifiés.
Les réglages HA, HTTPS, autorisations et écran sont conservés. **Show 2 reste
inaccessible ; sa dernière version vérifiée est `.4`.** La validation vocale
dans la pièce reste à effectuer.

[Activer la deuxième phrase](docs/wiki/Mixed-wake-words.md) ·
[Mesures et limites](docs/wiki/Validation.md#october-20-shutdown-checkpoint) ·
[Schéma de traitement](docs/assets/mixed-wake-pipeline.svg).
Les cinq langues des README et quatre langues de l’horloge sont maintenues.

## Étapes antérieures vérifiées

- [20 octobre, `.8`](docs/wiki/Validation.md#october-20-lifecycle-checkpoint) : remplacement sérialisé du détecteur et phrase principale désactivée.
- [19 octobre, `.7`](docs/wiki/Validation.md#october-19-mixed-wake-checkpoint) : première installation vérifiée de Myshka et Jarvis ensemble.
- [19 octobre, `.6`](docs/wiki/Validation.md#october-19-current-checkpoint) : mise à jour avec la signature précédente, HTTPS, fichiers de référence et mesures séparées du serveur vocal.
- [16 octobre, `.4`](docs/wiki/Validation.md#pr-69-follow-up-myshka4-build-and-show-2-checks) : liste des modèles et reprise du microphone sur Show 2.
- [16 octobre, `.3`](docs/wiki/Validation.md#october-16-installed-state-and-replay-checks) : comparaison de référence et cycles du microphone sur les deux Shows. Le [schéma à une phrase](docs/assets/exact-oww-pipeline.svg) décrit cette ancienne configuration.

Les journaux conservent leurs versions, dates et limites. Ils ne démontrent pas la reconnaissance acoustique avec un APK plus récent.

## Fonctions

- **Assist vocal :** détection ONNX exacte de **« Привет, мышка »** au seuil **0,50**, avec **« Hey Jarvis »** en option et sa propre décision temporelle calibrée. Le mode précédent à deux modèles microWakeWord reste disponible séparément. Les modèles privés ne sont pas distribués. [Voix et modèles](docs/wiki/Voice-and-wake-words.md).
- **Une interface adaptée aux cinq pouces :** grande horloge, caméra en plein écran lors d’un mouvement, affichage manuel temporaire et retour à l’horloge. Le lecteur conserve les proportions et attend une image présentée avant de révéler la vidéo. [Écran, médias et appels](docs/wiki/Display-media-and-calls.md).
- **Commande à distance depuis HA :** annonces, musique, flux TV configurés, client OTT-play-FOSS sur Capacitor, accès Web OTT séparé et OttPlayer en option. Home/Stop termine l’activité gérée. [Terminal à distance](docs/remote-endpoint.md).
- **Appels sur votre installation Jitsi :** salle définie, règle de participation choisie explicitement et gestion du microphone pendant puis après l’appel. L’interphone HA expérimental est un parcours distinct. [Jitsi et interphone](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Choix de l’assistant :** Homeway, le parcours cloud FCC indépendant, ou dialogue local et Silero avec reconnaissance vocale cloud FCC. La sélection se fait par satellite ; le basculement n’est pas automatique. [Changer d’assistant](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Langues :** cinq README d’entrée — anglais, russe, allemand, espagnol et français. L’interface de l’horloge propose actuellement **quatre langues : anglais, russe, allemand et espagnol**. Le français concerne la documentation uniquement. La langue d’affichage, la reconnaissance vocale et les phrases d’activation sont des réglages indépendants. [Portée de la localisation](docs/wiki/Localization.md).

## Anciennes vérifications de l’écran et de la voix

Le [journal du 15 octobre](docs/wiki/Validation.md#october-15-installed-state-and-recovery-checks) couvre `dualwake.2`, l’écran `20261015-r11`, 48 rendus synthétiques et les vérifications de reprise sur les appareils. Le [bilan du 14 octobre](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) conserve l’ancien parcours Piper/Irina et les annonces au niveau du service. L’[instantané de conversion du 2 octobre](docs/preparation-status.md) est historique.

La reconnaissance des phrases dans la pièce, la qualité audible, la reprise après une coupure de courant et le fonctionnement sur plusieurs jours restent des vérifications séparées. Les appels API terminés, les modèles chargés et les fichiers de test constituent des preuves plus limitées.

## Compatibilité et préparation

Ce parcours prend en charge **uniquement le Show 5 Gen2 / `cronos`**. Les images et commandes d’Echo Dot/EchoLocal, du Show 5 Gen1 ou du Show 8 ne sont pas interchangeables.

```text
cronos d’origine → amonet-cronos 2.0.1 → TWRP → sauvegarde externe vérifiée
                 → LineageOS 18.1 v0.4 / Android 11 → Companion + VACA en option
```

Le déverrouillage modifie la chaîne de démarrage **avant la première sauvegarde**. Android remplace Fire OS/Alexa et nécessite le formatage des données. La sauvegarde brute est faite après déverrouillage, exclut RPMB et ne démontre pas une méthode universelle de retour à l’état d’usine.

Il faut le **bloc d’alimentation normal**, un câble micro-USB **de données**, un Synology physique **x86_64** avec Docker, Python 3.8+, SSH et de l’espace de sauvegarde, un ordinateur avec Python/SSH/rsync et un serveur HA accessible. USB ne remplace pas le bloc d’alimentation. Téléchargez les artefacts séparément et vérifiez-les selon le guide.

Après la préparation de l’hôte dans le [guide d’installation](docs/runbook.md), ces commandes consultent l’état sans lancer la conversion :

```bash
python3 scripts/remote.py preflight
python3 scripts/remote.py inventory
```

Sélectionnez **le port USB physique observé et le numéro de série complet**, jamais « le premier Echo ». Les opérations d’écriture ont leurs propres commandes et contrôles ; brancher le câble ne déclenche pas une conversion.

## Documentation et maintenance

[Wiki](docs/wiki/Home.md) · [Processus et résultats](docs/wiki/Process-and-results.md) · [Diagrammes SVG](docs/assets/README.md) · [Index complet](docs/README.md) · [Architecture et limites du cloud](docs/wiki/Architecture.md) · [Mise à jour et récupération](docs/wiki/Installation-and-recovery.md) · [Dépannage](docs/wiki/Troubleshooting.md) · [Validation](docs/wiki/Validation.md) · [Localisation](docs/wiki/Localization.md) · [Maintenance](docs/wiki/Maintenance.md).

Placez les téléchargements dans `downloads/`, les sources tierces dans `vendor/`, les sauvegardes dans `backups/`, les journaux dans `logs/`, et les clés, enregistrements et configurations remplies dans `private/`. Git ignore ces emplacements, mais cela ne retire pas les données déjà suivies. Les fichiers HA sous `/local` sont accessibles sans authentification et ne doivent contenir aucun secret.

[Contributions et tests](CONTRIBUTING.md) · [Sécurité](SECURITY.md) · [Licences tierces](THIRD_PARTY_NOTICES.md) · [Versions](RELEASING.md) · [Politique de traduction](docs/i18n.md). Une version du projet contient les sources des intégrations, pas de firmware ni d’APK. La CI ne garantit pas le son audible ou la fiabilité d’un appareil donné.

## Projets associés

- [EchoMuse / emOS](https://github.com/ha-homelab/ha-echomuse)
- [Echo Dot 2 / EchoLocal](https://github.com/ha-homelab/ha-echo-dot)
- [Amazon Echo Home Energy / Alexa](https://github.com/4alvit/amazon-echo-home-voice)

EchoMuse avec emOS est une autre pile logicielle pour Dot. Sa configuration et sa récupération sont documentées dans son dépôt. Le projet Alexa conserve la plateforme d’origine ; il ne crée pas un satellite Assist.
