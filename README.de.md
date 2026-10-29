# Echo Show 5 Gen2 → Android → Home Assistant


[Current installed capabilities and expansion plan (English)](docs/installed-capabilities.md).
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15595/badge)](https://www.bestpractices.dev/projects/15595)

[English](README.md) · [Русский](README.ru.md) · **Deutsch** · [Español](README.es.md) · [Français](README.fr.md)

Dieses Projekt macht einen **Amazon Echo Show 5 der zweiten Generation (2021), Codename `cronos`**, zu einem Home-Assistant-Sprachsatelliten, einer gut lesbaren Uhr, einem Kamera-Bildschirm bei Bewegung und einem fernsteuerbaren Medien- und Anrufgerät. Das Repository enthält Werkzeuge für den begleiteten Umbau, lokale Patches, Integrationen und Wiederherstellungsanleitungen. Firmware, APKs, private Aktivierungsmodelle und Zugangsdaten sind nicht enthalten.

Beginnen Sie im [Projekt-Wiki](docs/wiki/Home.md). Für ein unverändertes Gerät gilt die [Umbauanleitung](docs/runbook.md); für ein Gerät mit Android die [Update- und Wiederherstellungsanleitung](docs/wiki/Installation-and-recovery.md). **Ein bereits entsperrtes Gerät nicht erneut entsperren.** Die ausführlichen technischen Anleitungen werden auf Englisch gepflegt; diese Seite ist der deutsche Einstieg.

![Architektur: Echo Show verbindet sich mit HA; Sprache, Kameras und Anrufe haben getrennte Datenwege. Die Grafik ist englisch beschriftet.](docs/assets/architecture.svg)


[![Uhranzeige in Perspektive](docs/assets/clock-hero.png)](docs/assets/clock-screenshot.jpg)

Die echte Uhrseite `20261015-r11`, aufgenommen in Desktop-Chrome mit
960 × 480 und der Beispielkonfiguration. Ohne Home-Assistant-Anmeldung, Kamera
oder Gerät. Ein Klick öffnet das flache Original.

## 20. Oktober: Listener-Wechsel auf Show 1 geprüft

**Show 1 verwendet `myshka.9` / `7009` mit „Привет, мышка“ und „Hey Jarvis“.**
Myshka bleibt bei **0,50**; Jarvis behält seinen eigenen Mittelwert über fünf
Auswertungen **> 0,97**. Ein Mikrofon versorgt beide Phrasen und den separaten
Stop-Befehl. Vor einem Listener-Wechsel wird die bisherige Erfassung geschlossen;
eine deaktivierte primäre Phrase startet keine Mikrofonerfassung.
Schlägt ein Schritt beim Beenden fehl, führt dieser Build die übrigen Aufräumschritte dennoch aus.

**62 JVM-Tests** und **sechs Android-Tests** bestanden. Auf dem Gerät wurden
Konfigurationswechsel ohne App-Neustart, die deaktivierte primäre Phrase,
**drei tatsächliche Mikrofon-Stummschaltzyklen** und ein App-Neustart geprüft.
HA-Einstellungen, HTTPS-Prüfung, Berechtigungen und Display blieben erhalten.
**Show 2 ist nicht erreichbar; zuletzt wurde `.4` geprüft.** Die praktische
Spracherkennung bleibt noch zu prüfen.

[Zweite Phrase aktivieren](docs/wiki/Mixed-wake-words.md) ·
[Messungen und Grenzen](docs/wiki/Validation.md#october-20-shutdown-checkpoint) ·
[Verarbeitungsdiagramm](docs/assets/mixed-wake-pipeline.svg).
Fünf README-Sprachen und vier Laufzeitsprachen der Uhr bleiben verfügbar.

## Frühere geprüfte Stände

- [20. Oktober, `.8`](docs/wiki/Validation.md#october-20-lifecycle-checkpoint): serialisierter Listener-Wechsel und deaktivierte primäre Phrase.
- [19. Oktober, `.7`](docs/wiki/Validation.md#october-19-mixed-wake-checkpoint): erste geprüfte gemeinsame Myshka/Jarvis-Installation.
- [19. Oktober, `.6`](docs/wiki/Validation.md#october-19-current-checkpoint): Update mit bisheriger Signatur, HTTPS, Referenzdateien und getrennte Messungen des Sprachservers.
- [16. Oktober, `.4`](docs/wiki/Validation.md#pr-69-follow-up-myshka4-build-and-show-2-checks): Modellliste und Wiederaufnahme der Mikrofonerfassung auf Show 2.
- [16. Oktober, `.3`](docs/wiki/Validation.md#october-16-installed-state-and-replay-checks): Referenzvergleich und Mikrofonzyklen auf beiden Shows. Das [Diagramm mit einer Phrase](docs/assets/exact-oww-pipeline.svg) beschreibt diese frühere Konfiguration.

Die Protokolle behalten ihre Versionen, Daten und Prüfgrenzen. Sie belegen keine akustische Erkennung mit einem späteren APK.

## Funktionen

- **Sprachgesteuerter Assist:** exakte ONNX-Erkennung von **„Привет, мышка“** mit **0,50** und optional **„Hey Jarvis“** mit eigener kalibrierter Entscheidung über mehrere Auswertungen. Der frühere Modus mit zwei microWakeWord-Modellen bleibt separat verfügbar. Private Modelle werden nicht verteilt. [Sprache und Modelle](docs/wiki/Voice-and-wake-words.md).
- **Oberfläche für fünf Zoll:** große Uhr, bildschirmfüllendes Front-/Porch-Kameravideo bei Bewegung, zeitlich begrenzte manuelle Ansicht und Rückkehr zur Uhr. Das Seitenverhältnis bleibt erhalten; Video erscheint erst mit einem verfügbaren Bild, ohne verzerrtes Android-Play-Symbol. [Bildschirm](docs/wiki/Display-media-and-calls.md).
- **HA-Fernbedienung:** Ansagen, Musik, fest konfigurierte TV-Streams, unser OTT-play-FOSS-Client auf Capacitor, ein separater OTT-Webzugang und optional OttPlayer. Home/Stop beendet die verwaltete Aktivität. [Fernsteuerung](docs/remote-endpoint.md).
- **Anrufe über die eigene Jitsi-Installation:** fester Raum, ausdrücklich gewählte Beitrittsregel, Mikrofonübergabe und Wiederherstellung nach dem Anruf. Die experimentelle HA-Gegensprechanlage ist ein gesonderter Weg. [Anrufe](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Sprachdienst auswählen:** Homeway, der unabhängige FCC-Cloud-Pfad oder lokaler Dialog und Silero mit FCC-Cloud-Spracherkennung. Die Auswahl gilt pro Satellit; es gibt kein automatisches Failover. [Umschalten](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Sprachen:** Einstiegs-READMEs auf Englisch, Russisch, Deutsch, Spanisch und Französisch sowie eine eigene Spracheinstellung für die Uhr. Bildschirm-, Erkennungs- und Aktivierungssprache sind unabhängig. [Lokalisierungsumfang](docs/wiki/Localization.md).

## Frühere Display- und Sprachprüfungen

Das [Protokoll vom 15. Oktober](docs/wiki/Validation.md#october-15-installed-state-and-recovery-checks) enthält `dualwake.2`, Display `20261015-r11`, 48 synthetische Layout-Renderings und die Geräteprüfung zur Wiederherstellung. Der [Stand vom 14. Oktober](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) dokumentiert die frühere Piper/Irina-Pipeline und Ansagen auf Dienstebene. Der [Konversionsstand vom 2. Oktober](docs/preparation-status.md) ist historisch.

Spracherkennung im Raum, hörbare Antwortqualität, Wiederherstellung nach Stromausfall und mehrtägiger Dauerbetrieb bleiben getrennte Prüfungen. Erfolgreiche API-Aufrufe, geladene Modelle und Testdateien belegen weniger.

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

### Room endpoint expansion

[Room controls and timers](docs/room-panel.md) · [Session policy](docs/room-session-policy.md) · [Remote administration](docs/remote-admin-tools.md) · [Capability delivery and limits](docs/room-capability-delivery.md)
