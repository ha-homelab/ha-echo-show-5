# Echo Show 5 Gen2 → Android → Home Assistant

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Dies ist ein übersetzter Überblick mit Einstiegspfad. Die ausführlichen Anleitungen und Befehle werden derzeit auf Englisch gepflegt und sind unten verlinkt. Die README-Sprache ändert weder Spracherkennung noch Antwortstimme oder Aktivierungswort.

Werkzeuge und eine betreute Schrittfolge für den **Echo Show 5 der zweiten Generation (2021), Codename `cronos`**. Mit Android kann das Gerät über Companion ein HA-Dashboard anzeigen und mit einer separat eingerichteten Assist-Pipeline als Sprachclient arbeiten. Dies ist ein eigener Display-Pfad, keine EchoLocal- oder EchoMuse-Firmware für einen Dot.

![Echo Show 5 Gen2 → Android → Home Assistant](docs/assets/architecture.svg)

## Erste Schritte

1. Bestätigen Sie **Gen2 / cronos**. Benötigt werden das originale Netzteil, ein Micro-USB-Datenkabel, ein physischer x86_64-Synology-Host mit Docker und Python 3.8+ sowie ein Rechner mit Python, SSH und rsync.
2. Beginnen Sie mit der [Installationsanleitung](docs/runbook.md): SSH-Ziel festlegen, festgelegte Artefakte laden und prüfen, Container vorbereiten. Wählen Sie den physischen USB-Port und die vollständig beobachtete Seriennummer, nicht das erste gefundene Gerät.
3. Führen Sie die Stufen getrennt aus: amonet-cronos 2.0.1 → TWRP → geprüftes externes Backup → LineageOS 18.1 v0.4 / Android 11 → Companion 2026.8.4 minimal. Bei bereits bestätigtem TWRP wird das Entsperren nicht wiederholt.
4. Verbinden Sie Android mit WLAN, melden Sie Companion bei HA an und prüfen Sie Dashboard und Berechtigungen. Sprache und Assist-Stufen stehen im [Android-/HA-Leitfaden](docs/android-and-home-assistant.md). VACA ist ein optionaler Weg zur dauerhaften Aktivierungsworterkennung.
5. Ergänzen Sie [Dashboard](docs/show-dashboard.md), [native Musikbefehle](docs/native-voice-controls.md), Kamera und Intercom einzeln. Prüfen Sie zuerst den Grundbetrieb, dann jede zusätzliche Funktion.

## Grenzen und Prüfung

Das Entsperren verändert die Bootkette bereits vor dem ersten Backup. Android ersetzt Fire OS und Alexa und erfordert das Formatieren der Daten. Das Raw-Backup entsteht nach dem Entsperren, enthält kein RPMB und garantiert keine allgemeine Wiederherstellung des Werkszustands. Historische Ergebnisse und offene Prüfungen stehen im Abnahmebericht; eine installierte App belegt weder akustische Erkennung noch mehrtägige Stabilität. Kamera, Intercom und Jitsi haben eigene Grenzen. Diese Anleitung gilt nicht für Dot-Geräte oder andere Show-Generationen.

## Ausführliche Dokumentation

- [Index](docs/README.md)
- [Prüfprotokoll](docs/preparation-status.md)
- [Aktivierungswort](docs/vaca-private-wakeword.md)
- [Kamera und Intercom](docs/camera-and-intercom.md)
- [Fernsteuerung](docs/remote-endpoint.md)
- [Alternativer Sprachpfad](docs/fcc-voice-backup.md)
- [Sicherheit](SECURITY.md)
- [Veröffentlichung und Releases](docs/release-packaging.md)
- [Beiträge und Übersetzung](docs/i18n.md)

## Verwandte Projekte

- [EchoMuse / emOS](https://github.com/ha-homelab/ha-echomuse)
- [Echo Dot 2 / EchoLocal](https://github.com/ha-homelab/ha-echo-dot)
- [Amazon Echo Home Energy / Alexa](https://github.com/4alvit/amazon-echo-home-voice)

EchoMuse mit emOS ist ein anderer Softwarestack für den Dot. Konfiguration, Zugriff und Wiederherstellung stehen im eigenen Repository. Das Alexa-Projekt behält die ursprüngliche Plattform und macht daraus keinen Assist-Satelliten.
