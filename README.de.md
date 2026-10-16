# Echo Show 5 Gen2 → Android → Home Assistant

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15595/badge)](https://www.bestpractices.dev/projects/15595)

[English](README.md) · [Русский](README.ru.md) · **Deutsch** · [Español](README.es.md) · [Français](README.fr.md)

Dieses Projekt macht einen **Amazon Echo Show 5 der zweiten Generation (2021), Codename `cronos`**, zu einem Home-Assistant-Sprachsatelliten, einer gut lesbaren Uhr, einem Kamera-Bildschirm bei Bewegung und einem fernsteuerbaren Medien- und Anrufgerät. Das Repository enthält Werkzeuge für den begleiteten Umbau, lokale Patches, Integrationen und Wiederherstellungsanleitungen. Firmware, APKs, private Aktivierungsmodelle und Zugangsdaten sind nicht enthalten.

Beginnen Sie im [Projekt-Wiki](docs/wiki/Home.md). Für ein unverändertes Gerät gilt die [Umbauanleitung](docs/runbook.md); für ein Gerät mit Android die [Update- und Wiederherstellungsanleitung](docs/wiki/Installation-and-recovery.md). **Ein bereits entsperrtes Gerät nicht erneut entsperren.** Die ausführlichen technischen Anleitungen werden auf Englisch gepflegt; diese Seite ist der deutsche Einstieg.

![Architektur: Echo Show verbindet sich mit HA; Sprache, Kameras und Anrufe haben getrennte Datenwege. Die Grafik ist englisch beschriftet.](docs/assets/architecture.svg)

## 16. Oktober: Versuch mit einer ONNX-Aktivierungsphrase

**Build geprüft; Geräteprüfungen stehen noch aus.** `0.13.4+myshka.3` / `7003` bestand **18 JVM-Tests ohne Fehler oder übersprungene Tests**. Der neue optionale Pfad soll ausschließlich **„Привет, мышка“** mit dem passenden ONNX-Frontend und einem Schwellwert von **0,50** (**5,0 in HA**) verwenden. „Hey Jarvis“ wird aus der aktiven Auswahl entfernt; der separate Stop-Befehl bleibt erhalten. Installation, Vergleich mit den Referenzausgaben und tatsächlich gesprochene Aktivierung sind noch nicht bestätigt. Zwei microWakeWord-Modelle bleiben als Funktion verfügbar; der geprüfte Stand vom 15. Oktober ist unten dokumentiert.

[Modellumstellung: Ablauf und Ergebnisse](docs/wiki/Wake-model-rollout.md) · [Technische Anleitung](docs/openwakeword-myshka.md) · [Prüfdiagramm](docs/assets/wake-validation.svg)

![Ein Mikrofon versorgt die exakte ONNX-Verarbeitung und den separaten Stop-Detektor. Ein 80-ms-Audioblock ist keine gemessene Aktivierungsverzögerung. Die Grafik ist englisch beschriftet.](docs/assets/exact-oww-pipeline.svg)

## Funktionen

- **Sprachgesteuerter Assist:** Der neue optionale ONNX-Pfad nutzt eine Aktivierungsphrase; die bestehende Funktion mit zwei microWakeWord-Modellen bleibt erhalten. Der geprüfte Stand vom 15. Oktober verwendet **„Привет, мышка“** und **„Hey Jarvis“** mit **0,35**. Im ONNX-Versuch gilt **0,50** für ein anderes Modell; daraus lässt sich keine vergleichbare Empfindlichkeit ableiten. Private Modelle werden nicht verteilt. [Sprache und Modelle](docs/wiki/Voice-and-wake-words.md).
- **Oberfläche für fünf Zoll:** große Uhr, bildschirmfüllendes Front-/Porch-Kameravideo bei Bewegung, zeitlich begrenzte manuelle Ansicht und Rückkehr zur Uhr. Das Seitenverhältnis bleibt erhalten; Video erscheint erst mit einem verfügbaren Bild, ohne verzerrtes Android-Play-Symbol. [Bildschirm](docs/wiki/Display-media-and-calls.md).
- **HA-Fernbedienung:** Ansagen, Musik, fest konfigurierte TV-Streams, unser OTT-play-FOSS-Client auf Capacitor, ein separater OTT-Webzugang und optional OttPlayer. Home/Stop beendet die verwaltete Aktivität. [Fernsteuerung](docs/remote-endpoint.md).
- **Anrufe über die eigene Jitsi-Installation:** fester Raum, ausdrücklich gewählte Beitrittsregel, Mikrofonübergabe und Wiederherstellung nach dem Anruf. Die experimentelle HA-Gegensprechanlage ist ein gesonderter Weg. [Anrufe](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Sprachdienst auswählen:** Homeway, der unabhängige FCC-Cloud-Pfad oder lokaler Dialog und Piper mit FCC-Cloud-Spracherkennung. Die Auswahl gilt pro Satellit; es gibt kein automatisches Failover. [Umschalten](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Sprachen:** Einstiegs-READMEs auf Englisch, Russisch, Deutsch, Spanisch und Französisch sowie eine eigene Spracheinstellung für die Uhr. Bildschirm-, Erkennungs- und Aktivierungssprache sind unabhängig. [Lokalisierungsumfang](docs/wiki/Localization.md).

## Stand der Prüfung

**Geprüfter Stand vom 15. Oktober 2026:** Der gebaute Patch `dualwake.2` korrigiert die Freigabe der Detektorressourcen. Die Bildschirmversion `20261015-r11` kombiniert Englisch, Russisch, Deutsch und Spanisch mit Wiederholungsversuchen, wenn der MQTT-Befehl beim HA-Start noch nicht verfügbar ist. In **48 synthetischen Desktop-Layout-Renderings** wurden in den geprüften Fällen keine abgeschnittenen Elemente festgestellt. Beide Updates waren zu diesem Prüfzeitpunkt auf beiden Shows installiert. Jedes Gerät bestand drei softwaregesteuerte Stumm-/Lautschaltzyklen des Mikrofons und einen App-Neustart; beide Modelle und die Aufnahme wurden wiederhergestellt. Die Erkennung tatsächlich gesprochener Phrasen bleibt ungeprüft; Details stehen im [Validierungsprotokoll](docs/wiki/Validation.md).

Der dokumentierte Stand vom **14. Oktober 2026** umfasst zwei Shows mit Android 11 / inoffiziellem LineageOS 18.1. Beide Aktivierungsmodelle wurden nach einem normalen **App-Neustart** geladen, die HA-Identitäten blieben erhalten, und aufeinanderfolgende Ansagen wurden auf Dienstebene abgeschlossen. Beide Geräte verwenden **Local Russian Home** und die Stimme **Irina**. Für die Spracherkennung wird weiterhin Audio in die Cloud gesendet. [Build-Nachweise](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) · [Sprachkonfiguration](docs/fcc-voice-backup.md).

**Gezielte Tests beider Phrasen am Gerät, hörbare Antwortqualität, Wiederanlauf nach Stromausfall und mehrtägiger Betrieb sind für den Build `dualwake.2` noch nicht bestätigt.** Ein API-Erfolg oder geladenes Modell ersetzt diese Tests nicht. Die [Validierungsübersicht](docs/wiki/Validation.md) trennt die Prüfumfänge. Der [Umbau-Schnappschuss vom 2. Oktober](docs/preparation-status.md) ist historisch und enthält inzwischen geänderte Spracheinstellungen.

## Kompatibilität und Vorbereitung

Unterstützt wird **nur Show 5 Gen2 / `cronos`**. Images und Verfahren für Echo Dot/EchoLocal, Show 5 Gen1 oder Show 8 sind nicht austauschbar.

```text
Unveränderter cronos → amonet-cronos 2.0.1 → TWRP → geprüfte externe Sicherung
                    → LineageOS 18.1 v0.4 / Android 11 → Companion + optional VACA
```

Das Entsperren verändert die Boot-Kette **vor der ersten Sicherung**. Android ersetzt Fire OS/Alexa und erfordert das Formatieren von Daten. Die Sicherung ist kein Nachweis einer allgemein getesteten Rückkehr zum Werkszustand. Erforderlich sind das normale **Netzteil**, ein Micro-USB-**Datenkabel**, ein physischer **x86_64**-Synology-NAS mit Docker/Python 3.8+/SSH und Sicherungsspeicher, ein Rechner mit Python/SSH/rsync sowie ein erreichbarer HA-Server. USB ersetzt das Netzteil nicht. Die benötigten Dateien werden separat heruntergeladen und gemäß Anleitung geprüft.

Nach der Vorbereitung des Hosts im [Runbook](docs/runbook.md) lesen diese Befehle nur den Zustand:

```bash
python3 scripts/remote.py preflight
python3 scripts/remote.py inventory
```

Wählen Sie den **beobachteten physischen USB-Port und die vollständige Seriennummer**, niemals „den ersten Echo“. Schreibvorgänge haben eigene Befehle und Prüfschranken; das Einstecken startet keinen Umbau.

## Dokumentation und Wartung

[Wiki](docs/wiki/Home.md) · [Architektur und Cloud-Grenzen](docs/wiki/Architecture.md) · [Installation und Rückkehr](docs/wiki/Installation-and-recovery.md) · [Sprache](docs/wiki/Voice-and-wake-words.md) · [Bildschirm, Medien, Anrufe](docs/wiki/Display-media-and-calls.md) · [Fehlersuche](docs/wiki/Troubleshooting.md) · [Validierung](docs/wiki/Validation.md) · [Lokalisierung](docs/wiki/Localization.md) · [Wartung](docs/wiki/Maintenance.md).

Downloads gehören nach `downloads/`, fremder Quellcode nach `vendor/`, Sicherungen nach `backups/`, Protokolle nach `logs/`, Schlüssel, Aufnahmen und ausgefüllte Konfigurationen nach `private/`. Git ignoriert diese Verzeichnisse, entfernt damit aber keine bereits eingecheckten Daten. HA-Dateien unter `/local` sind ohne Anmeldung erreichbar und dürfen keine Geheimnisse enthalten.

[Beiträge und Tests](CONTRIBUTING.md) · [Sicherheit](SECURITY.md) · [Drittlizenzen](THIRD_PARTY_NOTICES.md) · [Releases](RELEASING.md). Ein Projekt-Release enthält Integrationsquellen, keine Firmware und keine APK. CI bestätigt weder hörbaren Ton noch die Zuverlässigkeit eines konkreten Geräts.
