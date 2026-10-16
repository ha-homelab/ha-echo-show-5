# Echo Show 5 Gen2 → Android → Home Assistant

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Ce document est une présentation traduite accompagnée d’un parcours de démarrage. Les procédures détaillées et les commandes restent pour le moment maintenues en anglais ; les liens y renvoient. La langue du README ne change ni la reconnaissance, ni la voix de réponse, ni le mot d’activation.

Outils et procédure accompagnée pour **Echo Show 5 de deuxième génération (2021), nom de code `cronos`**. Avec Android, l’appareil peut afficher un tableau de bord HA via Companion et servir de client vocal avec Assist configuré séparément. Il s’agit d’un parcours distinct pour écran, pas d’un firmware EchoLocal ou EchoMuse pour Dot.

![Echo Show 5 Gen2 → Android → Home Assistant](docs/assets/architecture.svg)

## Premiers pas

1. Confirmez **Gen2 / cronos**. Il faut l’alimentation d’origine, un câble micro-USB de données, un Synology physique x86_64 avec Docker et Python 3.8+, et un ordinateur avec Python, SSH et rsync.
2. Suivez le [guide d’installation](docs/runbook.md) : configurez SSH, téléchargez et vérifiez les artefacts épinglés, puis préparez le conteneur. Choisissez le port USB physique et le numéro de série complet observé, jamais le premier appareil trouvé.
3. Exécutez séparément : amonet-cronos 2.0.1 → TWRP → sauvegarde externe vérifiée → LineageOS 18.1 v0.4 / Android 11 → Companion 2026.8.4 minimal. Si TWRP est déjà confirmé, ne répétez pas le déverrouillage.
4. Connectez Android au Wi-Fi, identifiez-vous dans Companion et vérifiez le tableau de bord et les autorisations. Réglez la langue et les étapes Assist avec le [guide Android et HA](docs/android-and-home-assistant.md). VACA est une option pour l’écoute continue de la phrase d’activation.
5. Ajoutez séparément le [tableau de bord](docs/show-dashboard.md), les [commandes musicales natives](docs/native-voice-controls.md), la caméra ou l’interphone. Validez d’abord le fonctionnement de base, puis chaque fonction supplémentaire.

## Limites et validation

Le déverrouillage modifie la chaîne de démarrage avant la première sauvegarde. Android remplace Fire OS et Alexa et exige le formatage des données. La sauvegarde brute est faite après déverrouillage, exclut RPMB et ne garantit pas un retour universel à l’état d’usine. Les résultats historiques et les essais manquants figurent dans le rapport de validation ; une application installée ne prouve ni la précision acoustique ni la stabilité sur plusieurs jours. Caméra, interphone et Jitsi ont leurs propres limites. N’appliquez pas cette procédure aux Dot ou à d’autres générations de Show.

## Documentation détaillée

- [Index](docs/README.md)
- [Rapport de validation](docs/preparation-status.md)
- [Phrase d’activation](docs/vaca-private-wakeword.md)
- [Caméra et interphone](docs/camera-and-intercom.md)
- [Commande à distance](docs/remote-endpoint.md)
- [Parcours vocal de secours](docs/fcc-voice-backup.md)
- [Sécurité](SECURITY.md)
- [Publication et versions](docs/release-packaging.md)
- [Contributions et traduction](docs/i18n.md)

## Projets associés

- [EchoMuse / emOS](https://github.com/ha-homelab/ha-echomuse)
- [Echo Dot 2 / EchoLocal](https://github.com/ha-homelab/ha-echo-dot)
- [Amazon Echo Home Energy / Alexa](https://github.com/4alvit/amazon-echo-home-voice)

EchoMuse avec emOS est une autre pile logicielle pour Dot. Sa configuration, ses accès et sa récupération sont documentés dans son dépôt. Le projet Alexa conserve la plateforme d’origine ; il ne crée pas un satellite Assist.
