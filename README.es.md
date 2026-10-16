# Echo Show 5 Gen2 → Android → Home Assistant

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Este documento es una introducción traducida con una ruta de inicio. Las instrucciones detalladas y los comandos se mantienen por ahora en inglés y están enlazados abajo. El idioma del README no cambia el reconocimiento, la voz de respuesta ni la frase de activación.

Herramientas e instrucciones supervisadas para **Echo Show 5 de segunda generación (2021), nombre en clave `cronos`**. Con Android puede mostrar un panel de HA mediante Companion y actuar como cliente de voz con Assist configurado por separado. Es una ruta independiente para pantallas, no firmware EchoLocal o EchoMuse para Dot.

![Echo Show 5 Gen2 → Android → Home Assistant](docs/assets/architecture.svg)

## Primeros pasos

1. Confirme **Gen2 / cronos**. Necesita la fuente original, un cable micro-USB de datos, un Synology físico x86_64 con Docker y Python 3.8+, y un ordenador con Python, SSH y rsync.
2. Siga la [guía de instalación](docs/runbook.md): configure SSH, descargue y verifique los artefactos fijados y prepare el contenedor. Seleccione el puerto USB físico y el número de serie completo observado, no el primer dispositivo encontrado.
3. Ejecute las etapas por separado: amonet-cronos 2.0.1 → TWRP → copia externa verificada → LineageOS 18.1 v0.4 / Android 11 → Companion 2026.8.4 minimal. Si TWRP ya está confirmado, no repita el desbloqueo.
4. Conecte Android a Wi-Fi, inicie sesión en HA con Companion y compruebe panel y permisos. Configure el idioma y las etapas de Assist con la [guía Android y HA](docs/android-and-home-assistant.md). VACA es una opción para escuchar continuamente la frase de activación.
5. Añada por separado el [panel](docs/show-dashboard.md), los [comandos nativos de música](docs/native-voice-controls.md), cámara o intercomunicador. Verifique primero el funcionamiento básico y después cada función adicional.

## Límites y validación

El desbloqueo modifica la cadena de arranque antes de la primera copia. Android sustituye Fire OS y Alexa y requiere formatear los datos. La copia raw es posterior al desbloqueo, excluye RPMB y no garantiza una restauración universal al estado de fábrica. Los resultados históricos y las pruebas pendientes están en el informe de aceptación; una aplicación instalada no demuestra precisión acústica ni estabilidad durante días. Cámara, intercomunicador y Jitsi tienen límites propios. No aplique este procedimiento a Dot ni a otras generaciones de Show.

## Documentación detallada

- [Índice](docs/README.md)
- [Registro de validación](docs/preparation-status.md)
- [Frase de activación](docs/vaca-private-wakeword.md)
- [Cámara e intercomunicador](docs/camera-and-intercom.md)
- [Control remoto](docs/remote-endpoint.md)
- [Ruta de voz alternativa](docs/fcc-voice-backup.md)
- [Seguridad](SECURITY.md)
- [Publicación y versiones](docs/release-packaging.md)
- [Contribuciones y traducción](docs/i18n.md)

## Proyectos relacionados

- [EchoMuse / emOS](https://github.com/ha-homelab/ha-echomuse)
- [Echo Dot 2 / EchoLocal](https://github.com/ha-homelab/ha-echo-dot)
- [Amazon Echo Home Energy / Alexa](https://github.com/4alvit/amazon-echo-home-voice)

EchoMuse con emOS es otra plataforma de software para Dot. Su configuración, acceso y recuperación se documentan en su propio repositorio. El proyecto Alexa conserva la plataforma original; no la convierte en un satélite Assist.
