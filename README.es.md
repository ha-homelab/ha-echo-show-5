# Echo Show 5 Gen2 → Android → Home Assistant


[Current delivery, acceptance results and limitations (English)](docs/room-capability-delivery.md).
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15595/badge)](https://www.bestpractices.dev/projects/15595)

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · **Español** · [Français](README.fr.md)

Este proyecto reutiliza un **Amazon Echo Show 5 de segunda generación (2021), nombre en clave `cronos`**, como satélite de voz de Home Assistant, reloj legible, pantalla de cámaras por movimiento y terminal de medios y llamadas con control remoto. El repositorio incluye herramientas de conversión supervisada, parches locales, integraciones e instrucciones de recuperación. No incluye firmware, APK, modelos privados de activación ni credenciales domésticas.

Empiece por la [wiki del proyecto](docs/wiki/Home.md). Para un dispositivo de fábrica, siga la [guía de conversión](docs/runbook.md); si ya tiene Android, use la [guía de actualización y recuperación](docs/wiki/Installation-and-recovery.md). **No vuelva a desbloquear un dispositivo ya convertido.** Las instrucciones técnicas detalladas se mantienen en inglés; esta página es el punto de entrada en español.

![Arquitectura: Echo Show se conecta con HA; voz, cámaras y llamadas siguen rutas de datos separadas. Las etiquetas del diagrama están en inglés.](docs/assets/architecture.svg)


[![Pantalla del reloj en perspectiva](docs/assets/clock-hero.png)](docs/assets/clock-screenshot.jpg)

La página real del reloj `20261015-r11`, capturada en Chrome de escritorio a
960 × 480 con la configuración de ejemplo. Sin iniciar sesión en Home Assistant,
ni usar cámara o dispositivo. Haz clic para ver el original.

## 20 de octubre: ciclo del detector verificado en Show 1

**Show 1 utiliza `myshka.9` / `7009` con «Привет, мышка» y «Hey Jarvis».**
Myshka conserva **0,50**; Jarvis mantiene su media independiente de cinco
evaluaciones **> 0,97**. Un micrófono alimenta ambas frases y el comando Stop
separado. La actualización espera el cierre del detector anterior y no inicia
la captura cuando la frase principal está desactivada.
Si falla un paso al detenerse, esta versión ejecuta los demás pasos de liberación de recursos.

Pasaron **62 pruebas JVM** y **seis pruebas Android**. Se comprobaron cambios
de configuración sin reiniciar la aplicación, la frase principal desactivada,
**tres ciclos reales de cierre y reapertura del micrófono** y un reinicio de la
aplicación. Se conservaron HA, verificación HTTPS, permisos y pantalla.
**Show 2 sigue inaccesible; su última versión verificada es `.4`.** La prueba
de voz en la habitación sigue pendiente.

[Activar la segunda frase](docs/wiki/Mixed-wake-words.md) ·
[Mediciones y límites](docs/wiki/Validation.md#october-20-shutdown-checkpoint) ·
[Diagrama de procesamiento](docs/assets/mixed-wake-pipeline.svg).
Se mantienen cinco idiomas de README y cuatro de la interfaz del reloj.

## Etapas anteriores verificadas

- [20 de octubre, `.8`](docs/wiki/Validation.md#october-20-lifecycle-checkpoint): reemplazo serializado del detector y frase principal desactivada.
- [19 de octubre, `.7`](docs/wiki/Validation.md#october-19-mixed-wake-checkpoint): primera instalación verificada de Myshka y Jarvis juntos.
- [19 de octubre, `.6`](docs/wiki/Validation.md#october-19-current-checkpoint): actualización con la firma anterior, HTTPS, archivos de referencia y mediciones independientes del servidor de voz.
- [16 de octubre, `.4`](docs/wiki/Validation.md#pr-69-follow-up-myshka4-build-and-show-2-checks): lista de modelos y recuperación del micrófono en Show 2.
- [16 de octubre, `.3`](docs/wiki/Validation.md#october-16-installed-state-and-replay-checks): comparación con la referencia y ciclos del micrófono en ambos Shows. El [diagrama de una frase](docs/assets/exact-oww-pipeline.svg) describe aquella configuración.

Los registros conservan sus versiones, fechas y límites. No demuestran reconocimiento acústico en un APK posterior.

## Funciones

- **Assist por voz:** detección ONNX exacta de **«Привет, мышка»** con **0,50** y **«Hey Jarvis»** opcional con su propia decisión temporal calibrada. El modo anterior con dos modelos microWakeWord sigue disponible por separado. Los modelos privados no se distribuyen. [Voz y modelos](docs/wiki/Voice-and-wake-words.md).
- **Interfaz para cinco pulgadas:** reloj grande, vídeo Front/Porch a pantalla completa al detectar movimiento, vista manual limitada en el tiempo y regreso al reloj. Se conserva la proporción; el vídeo aparece cuando hay un fotograma listo, sin el icono Play de Android deformado. [Pantalla](docs/wiki/Display-media-and-calls.md).
- **Control desde HA:** anuncios, música, canales de TV predefinidos, nuestro cliente OTT-play FOSS sobre Capacitor, una ruta web OTT independiente y OttPlayer opcional. Home/Stop termina la actividad administrada. [Control remoto](docs/remote-endpoint.md).
- **Llamadas mediante su propio Jitsi:** sala fija, política de entrada explícita, cesión del micrófono y restauración tras la llamada. El intercomunicador experimental de HA es una opción separada. [Llamadas](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Selección del servicio de voz:** Homeway, la ruta FCC independiente en la nube, o diálogo local y Silero con reconocimiento de voz FCC en la nube. Se elige por satélite; no hay conmutación automática al fallar. [Cambiar de asistente](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Idiomas:** README de entrada en inglés, ruso, alemán, español y francés, y configuración propia del idioma del reloj. El idioma de pantalla no cambia el reconocimiento ni la frase de activación. [Cobertura de localización](docs/wiki/Localization.md).

## Pruebas anteriores de pantalla y voz

El [registro del 15 de octubre](docs/wiki/Validation.md#october-15-installed-state-and-recovery-checks) cubre `dualwake.2`, la pantalla `20261015-r11`, 48 renderizados sintéticos y la recuperación comprobada en los dispositivos. El [registro del 14 de octubre](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) conserva la ruta anterior Piper/Irina y los anuncios a nivel de servicio. La [instantánea de conversión del 2 de octubre](docs/preparation-status.md) es histórica.

El reconocimiento de frases en la habitación, la calidad audible, la recuperación tras un corte eléctrico y el funcionamiento durante varios días siguen siendo pruebas separadas. Las llamadas API completadas, los modelos cargados y los archivos de prueba aportan evidencia más limitada.

## Compatibilidad y preparación

Se admite **solo Show 5 Gen2 / `cronos`**. Las imágenes y procedimientos de Echo Dot/EchoLocal, Show 5 Gen1 o Show 8 no son intercambiables.

```text
cronos de fábrica → amonet-cronos 2.0.1 → TWRP → copia externa verificada
                  → LineageOS 18.1 v0.4 / Android 11 → Companion + VACA opcional
```

El desbloqueo modifica la cadena de arranque **antes de la primera copia de seguridad**. Android sustituye Fire OS/Alexa y requiere formatear los datos. La copia no demuestra un procedimiento universal y probado de vuelta al sistema de fábrica. Se necesitan el **adaptador de corriente** normal, un cable micro-USB **de datos**, un Synology físico **x86_64** con Docker/Python 3.8+/SSH y espacio privado para copias, un ordenador con Python/SSH/rsync y un servidor HA accesible. USB no sustituye al adaptador. Los archivos se descargan y verifican por separado siguiendo la guía.

Después de preparar el host según el [runbook](docs/runbook.md), estos comandos solo consultan su estado:

```bash
python3 scripts/remote.py preflight
python3 scripts/remote.py inventory
```

Seleccione el **puerto USB físico observado y el número de serie completo**, nunca «el primer Echo». Las escrituras tienen comandos y comprobaciones separados; conectar el cable no inicia la conversión.

## Documentación y mantenimiento

[Wiki](docs/wiki/Home.md) · [arquitectura y límites de la nube](docs/wiki/Architecture.md) · [instalación y recuperación](docs/wiki/Installation-and-recovery.md) · [voz](docs/wiki/Voice-and-wake-words.md) · [pantalla, medios, llamadas](docs/wiki/Display-media-and-calls.md) · [diagnóstico](docs/wiki/Troubleshooting.md) · [validación](docs/wiki/Validation.md) · [localización](docs/wiki/Localization.md) · [mantenimiento](docs/wiki/Maintenance.md).

Guarde descargas en `downloads/`, fuentes externas en `vendor/`, copias en `backups/`, registros en `logs/` y claves, grabaciones y configuraciones rellenadas en `private/`. Git ignora estos directorios, pero `.gitignore` no elimina datos ya confirmados. Los archivos de HA bajo `/local` son públicos sin autenticación: no deben contener secretos.

[Contribuciones y pruebas](CONTRIBUTING.md) · [seguridad](SECURITY.md) · [licencias externas](THIRD_PARTY_NOTICES.md) · [publicaciones](RELEASING.md). Una publicación del proyecto contiene fuentes de integración, no firmware ni APK. CI no confirma sonido audible ni fiabilidad física de un dispositivo concreto.

### Room endpoint expansion

[Room controls and timers](docs/room-panel.md) · [Session policy](docs/room-session-policy.md) · [Remote administration](docs/remote-admin-tools.md) · [Capability delivery and limits](docs/room-capability-delivery.md)

[Selección del dispositivo que responde: VACA y TECHO5 (inglés)](docs/nearest-device-arbitration.md).
