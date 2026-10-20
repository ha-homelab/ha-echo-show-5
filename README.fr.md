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

## 19 octobre : deux phrases d’activation sur Show 1

**Show 1 utilise maintenant `myshka.7` / `7007` avec « Привет, мышка » et « Hey Jarvis » activés.**
Le traitement ONNX exact de Myshka conserve le seuil **0,50**. Jarvis applique
son propre calibrage : la probabilité moyenne sur **cinq évaluations doit être
strictement supérieure à 0,97**. Les deux utilisent un seul microphone ; Jarvis
partage le MicroFrontend existant avec Stop, qui reste une commande de lecture
indépendante.

La compilation avec la signature précédente a réussi **42 tests JVM** ; Show 1
a réussi **six tests Android**, **trois cycles de fermeture et de reprise réelles
de la capture du microphone** et un **redémarrage de l’application**. Les deux
modèles d’activation, Stop et l’authentification HTTPS ont été rétablis ; les
réglages sont conservés. **Show 2 reste inaccessible ; sa dernière version
vérifiée est `.4`.** Les tests synthétiques et les modèles chargés ne prouvent
pas la reconnaissance vocale dans la pièce ; la vérification en conditions
réelles reste à faire.

[Activer ou retirer la deuxième phrase](docs/wiki/Mixed-wake-words.md) ·
[Mesures et limites](docs/wiki/Validation.md#october-19-mixed-wake-checkpoint) ·
[Schéma de traitement](docs/assets/mixed-wake-pipeline.svg), en anglais.
Les cinq langues des README et les quatre langues de l’horloge restent inchangées.

## 19 octobre : état précédent avec myshka.6

À cette étape précédente, **VACA `0.13.4+myshka.6` / `7006`** a été installé sur Show 1 avec le certificat de signature précédent. **29 tests JVM** et **trois tests d’instrumentation Android** ont réussi. Lors de la lecture des quatre fichiers de test privés existants, toutes les décisions de seuil correspondaient à la référence. « Привет, мышка » au seuil **0,50** et le détecteur Stop séparé sont chargés ; la capture du microphone est active. Un cycle de coupure et de réactivation a confirmé la fermeture et la reprise de la capture, puis un redémarrage normal de l’application a confirmé une nouvelle authentification HTTPS ; les réglages HA, la luminosité manuelle à 255, les autorisations et ADB sécurisé sans root ont été conservés.

Show 2 est actuellement inaccessible sur le réseau et dans HA ; sa dernière version vérifiée est **`.4`**. La vérification du serveur a obtenu une réponse à une requête textuelle traitée par les fonctions natives de HA et téléchargé la voix Silero ; la vérification complète du serveur, de la requête textuelle au téléchargement de la voix, a pris **4,481 s**. Cela ne prouve ni une réponse audible ni la reconnaissance de la phrase prononcée dans la pièce. **La vérification vocale en conditions réelles reste à faire.** Les résultats de cette étape et leurs limites figurent dans le [journal du 19 octobre](docs/wiki/Validation.md#october-19-current-checkpoint). Les résultats ci-dessous concernent les dates et versions indiquées.

## 16 octobre : essai avec une seule phrase ONNX

### Correctif de la PR #69 : myshka.4

**`0.13.4+myshka.4` / `7004` est installé et vérifié localement sur Show 2.** Le certificat de signature est conservé et les **18 tests JVM** passent. Show 2 a réussi la régression Android ciblée sur la liste des modèles : **un test, cinq cas de métadonnées, 0,624 seconde**. Des métadonnées facultatives invalides ne font plus disparaître les modèles personnalisés ; le moteur rejette toujours les fichiers invalides lors du chargement. Show 2 a également réussi un cycle de fermeture et de reprise réelle de la capture du microphone ainsi qu’un redémarrage normal de l’application. Les réglages, la luminosité, les autorisations et ADB authentifié sans root ont été conservés. La vérification vocale de bout en bout reste à faire. Lors de la vérification du 16 octobre, Show 1 était inaccessible ; sa dernière version vérifiée à cette date était `.3`. La comparaison de référence de `.3` ci-dessous ne démontre pas une nouvelle comparaison sous `.4`.

### Bilan vérifié de myshka.3

**APK installé sur les deux Shows ; comparaison avec la référence réussie sur chacun.** VACA `0.13.4+myshka.3` / `7003` a passé **18 tests JVM**. Chaque Show a également passé **deux tests d’instrumentation Android** avec **quatre fichiers privés existants : 294 embeddings, 234 fenêtres du classificateur et 11 fenêtres positives**. Toutes les décisions de seuil correspondent à la référence. La lecture de fichiers n’enregistre pas la pièce et ne démontre pas la reconnaissance acoustique.

Au 16 octobre, les deux Shows étaient configurés uniquement pour **« Привет, мышка »**, avec le prétraitement ONNX exact et un seuil de **0,50** (**5,0 dans HA**). « Hey Jarvis » a été retiré de la sélection active ; la commande Stop séparée est conservée. **Les deux ont passé trois cycles de coupure/réactivation du microphone avec fermeture et reprise de la capture vérifiées, ainsi qu’un redémarrage normal de l’application.** Les réglages HA, la luminosité, les autorisations et ADB sans root ont été conservés. L’activation parlée, la réponse audible, la distance, Stop pendant la lecture, les coupures de courant et plusieurs jours d’utilisation restent à vérifier. La fonction à deux modèles microWakeWord et le bilan du 15 octobre restent documentés ci-dessous.

[Changement de modèle : processus et résultats](docs/wiki/Wake-model-rollout.md) · [Guide technique](docs/openwakeword-myshka.md) · [Graphique de validation](docs/assets/wake-validation.svg)

![Un microphone alimente le traitement ONNX exact et le détecteur Stop séparé. Le bloc audio de 80 ms ne représente pas une latence d’activation mesurée. Les légendes sont en anglais.](docs/assets/exact-oww-pipeline.svg)

## Fonctions

- **Assist vocal :** détection ONNX exacte de **« Привет, мышка »** au seuil **0,50**, avec **« Hey Jarvis »** en option et sa propre décision temporelle calibrée. Le mode précédent à deux modèles microWakeWord reste disponible séparément. Les modèles privés ne sont pas distribués. [Voix et modèles](docs/wiki/Voice-and-wake-words.md).
- **Une interface adaptée aux cinq pouces :** grande horloge, caméra en plein écran lors d’un mouvement, affichage manuel temporaire et retour à l’horloge. Le lecteur conserve les proportions et attend une image présentée avant de révéler la vidéo. [Écran, médias et appels](docs/wiki/Display-media-and-calls.md).
- **Commande à distance depuis HA :** annonces, musique, flux TV configurés, client OTT-play-FOSS sur Capacitor, accès Web OTT séparé et OttPlayer en option. Home/Stop termine l’activité gérée. [Terminal à distance](docs/remote-endpoint.md).
- **Appels sur votre installation Jitsi :** salle définie, règle de participation choisie explicitement et gestion du microphone pendant puis après l’appel. L’interphone HA expérimental est un parcours distinct. [Jitsi et interphone](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Choix de l’assistant :** Homeway, le parcours cloud FCC indépendant, ou dialogue local et Piper avec reconnaissance vocale cloud FCC. La sélection se fait par satellite ; le basculement n’est pas automatique. [Changer d’assistant](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Langues :** cinq README d’entrée — anglais, russe, allemand, espagnol et français. L’interface de l’horloge propose actuellement **quatre langues : anglais, russe, allemand et espagnol**. Le français concerne la documentation uniquement. La langue d’affichage, la reconnaissance vocale et les phrases d’activation sont des réglages indépendants. [Portée de la localisation](docs/wiki/Localization.md).

## État de la validation

**Bilan vérifié du 15 octobre 2026 :** les deux Shows ont reçu **VACA `0.13.4+dualwake.2` / code `7002`** et l’interface **`20261015-r11`**. Le correctif Android libère correctement les ressources des détecteurs. L’interface réessaie les abonnements lorsqu’une commande MQTT n’est pas encore disponible pendant le démarrage de HA. Sur chaque appareil, **trois cycles logiciels de coupure/réactivation du microphone et un redémarrage normal de l’application** ont restauré les deux modèles et la capture du microphone. L’affichage reste en anglais, au format 24 heures.

Les **48 rendus synthétiques sur navigateur de bureau** n’ont montré ni découpage des éléments ni retour à la ligne de l’horloge dans les cas testés. Ils ne prouvent pas le rendu de chaque langue sur Android. Les résultats des caméras, les versions installées et les limites des essais sont détaillés dans le [rapport de validation](docs/wiki/Validation.md) et le [récit du processus et des résultats](docs/wiki/Process-and-results.md).

**La reconnaissance des deux phrases prononcées volontairement devant l’appareil, la qualité audible des réponses, la reprise après coupure de courant et la stabilité sur plusieurs jours restent à valider pour la version `dualwake.2`.** Un modèle chargé ou un appel API réussi ne remplace pas ces essais. La reconnaissance vocale du parcours russe sélectionné envoie toujours l’audio dans le cloud ; le dialogue local et la synthèse locale ne rendent pas l’ensemble du parcours hors ligne. [Parcours vocaux](docs/fcc-voice-backup.md).

Le [bilan de conversion du 2 octobre](docs/preparation-status.md) et les [observations du 14 octobre](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) restent des documents historiques, avec leurs propres versions et conditions de test.

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
