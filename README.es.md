# Echo Show 5 Gen2 → Android → Home Assistant

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15595/badge)](https://www.bestpractices.dev/projects/15595)

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · **Español** · [Français](README.fr.md)

Este proyecto reutiliza un **Amazon Echo Show 5 de segunda generación (2021), nombre en clave `cronos`**, como satélite de voz de Home Assistant, reloj legible, pantalla de cámaras por movimiento y terminal de medios y llamadas con control remoto. El repositorio incluye herramientas de conversión supervisada, parches locales, integraciones e instrucciones de recuperación. No incluye firmware, APK, modelos privados de activación ni credenciales domésticas.

Empiece por la [wiki del proyecto](docs/wiki/Home.md). Para un dispositivo de fábrica, siga la [guía de conversión](docs/runbook.md); si ya tiene Android, use la [guía de actualización y recuperación](docs/wiki/Installation-and-recovery.md). **No vuelva a desbloquear un dispositivo ya convertido.** Las instrucciones técnicas detalladas se mantienen en inglés; esta página es el punto de entrada en español.

![Arquitectura: Echo Show se conecta con HA; voz, cámaras y llamadas siguen rutas de datos separadas. Las etiquetas del diagrama están en inglés.](docs/assets/architecture.svg)

## Funciones

- **Dos frases de activación simultáneas:** la extensión local de VACA usa un micrófono y dos modelos microWakeWord. La configuración documentada reconoce **«Привет, мышка»** y **«Hey Jarvis»**, con un umbral compartido de **0,35**. El modelo ruso privado no se distribuye. [Voz y modelos](docs/wiki/Voice-and-wake-words.md).
- **Interfaz para cinco pulgadas:** reloj grande, vídeo Front/Porch a pantalla completa al detectar movimiento, vista manual limitada en el tiempo y regreso al reloj. Se conserva la proporción; el vídeo aparece cuando hay un fotograma listo, sin el icono Play de Android deformado. [Pantalla](docs/wiki/Display-media-and-calls.md).
- **Control desde HA:** anuncios, música, canales de TV predefinidos, nuestro cliente OTT-play FOSS sobre Capacitor, una ruta web OTT independiente y OttPlayer opcional. Home/Stop termina la actividad administrada. [Control remoto](docs/remote-endpoint.md).
- **Llamadas mediante su propio Jitsi:** sala fija, política de entrada explícita, cesión del micrófono y restauración tras la llamada. El intercomunicador experimental de HA es una opción separada. [Llamadas](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Selección del servicio de voz:** Homeway, la ruta FCC independiente en la nube, o diálogo local y Piper con reconocimiento de voz FCC en la nube. Se elige por satélite; no hay conmutación automática al fallar. [Cambiar de asistente](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Idiomas:** README de entrada en inglés, ruso, alemán, español y francés, y configuración propia del idioma del reloj. El idioma de pantalla no cambia el reconocimiento ni la frase de activación. [Cobertura de localización](docs/wiki/Localization.md).

## Estado de las pruebas

**Actualización del 15 de octubre de 2026:** el parche compilado `dualwake.2` corrige la liberación de recursos del detector. La revisión de pantalla `20261015-r11` combina inglés, ruso, alemán y español con reintentos cuando el comando MQTT todavía no está disponible durante el arranque de HA. En **48 renderizados sintéticos de diseño en ordenador** no se observaron elementos recortados en los casos probados. Ambas actualizaciones están instaladas en los dos Shows. Cada dispositivo superó tres ciclos de silenciar/reactivar el micrófono por software y un reinicio de la aplicación; ambos modelos y la captura se recuperaron. El reconocimiento de frases pronunciadas sigue sin verificar; los detalles están en la [guía de validación](docs/wiki/Validation.md).

La referencia documentada del **14 de octubre de 2026** incluye dos Shows con Android 11 / LineageOS 18.1 no oficial. Ambos modelos de activación se cargaron después de un **reinicio normal de la aplicación**, se conservaron las identidades de HA y los anuncios consecutivos terminaron correctamente a nivel de servicio. Ambos dispositivos usan **Local Russian Home** y la voz **Irina**. El reconocimiento todavía envía audio a la nube. [Evidencia de compilación](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) · [historial de voz](docs/fcc-voice-backup.md).

**Siguen pendientes la prueba deliberada de ambas frases junto al dispositivo, la calidad audible, la recuperación tras un corte de corriente y varios días de funcionamiento de la nueva compilación.** Una llamada API correcta o un modelo cargado no demuestran estos resultados. La [guía de validación](docs/wiki/Validation.md) distingue los alcances. La [referencia de conversión del 2 de octubre](docs/preparation-status.md) es histórica y contiene ajustes de voz que ya han cambiado.

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
