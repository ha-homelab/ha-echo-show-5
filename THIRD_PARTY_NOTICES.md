# Third-party source and artifact notices

The following notices apply to upstream material included or referenced by this
repository. They do not select a license for this project's original helpers
and documentation; that separate owner decision is still pending.

## Included patch fragments

`patches/ottplay-foss-capacitor-startup.patch` and
`patches/ottplay-foss-capacitor-remote-control.patch` contain source context and
adapted code from [OTT-play FOSS](https://github.com/open-ott-play/ottplay-foss).
Copyright (c) 2026 open-ott-play. The [full MIT license](licenses/ottplay-foss-MIT.txt)
is preserved here. The documented base is
[`f8634903aa051592ccf15f675b8d8df3212fe502`](https://github.com/open-ott-play/ottplay-foss/tree/f8634903aa051592ccf15f675b8d8df3212fe502);
the remote-control adaptation includes changes from
[`a18cd4c5c9982ef5c8776c9fb7cc2076ba7de05e`](https://github.com/open-ott-play/ottplay-foss/tree/a18cd4c5c9982ef5c8776c9fb7cc2076ba7de05e).
The patch additions and removals identify local modifications.

`integrations/show5-display/vaca_dashboard_patch.py` includes source fragments
from the [View Assist Companion App Home Assistant integration](https://github.com/msp1974/ViewAssist_Companion_App/tree/4948528bd016c24c395bf8dc3d86c1c7ec60eb73)
by its upstream contributors, version 0.13.4. Those fragments and their local
per-entry-dashboard modifications remain subject to the
[Apache License 2.0](licenses/ViewAssist-Apache-2.0.txt). The reviewed upstream
commit contains a LICENSE file and no separate NOTICE file. The helper identifies
original and modified hashes and emits the changes as a guarded local patch.

## Referenced downloads

Firmware, recovery images, APKs, trained weights, recordings and device backups
are not redistributed by these notices. Artifact JSON records identify external
sources and downloaded-file digests; a digest does not grant redistribution
rights or certify a reproducible build.

The Android [ViewAssistCompanionApp](https://github.com/msp1974/ViewAssistCompanionApp/tree/65906aebffd2f39772773b44729b22fd022a1f3c)
is a separate Apache-2.0 project from the Home Assistant integration. The linked
[android-ip-camera](https://github.com/DigitallyRefined/android-ip-camera/tree/4a723736d207f3a44bffb3d99417c9b30309f993)
source uses MIT. The referenced [amonet](https://github.com/R0rt1z2/amonet/tree/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d)
source includes GPL-2.0 terms in `LICENSE.GPL2`; this does not establish a grant
for every downloaded proprietary payload. Preserve component notices and review
the actual distribution contents before redistributing any built image.
