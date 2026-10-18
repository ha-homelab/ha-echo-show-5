# Clock screenshot artwork

The cover uses the actual `integrations/show5-display` page from commit
`10f0151`, revision `20261015-r11`, rendered by desktop Chrome at 960 × 480
(2:1). Only `config.example.js` was copied to the local preview as `config.js`;
all page scripts and styles were unchanged. No HA credentials, camera feed,
remote event or physical device participated. The displayed date and time
are the browser clock at capture, not a benchmark or device test.

To capture an updated source, copy the display assets and example configuration
to a temporary local directory, serve it on localhost, and open the page at the
same viewport in a browser. Save a page-only screenshot as
`docs/assets/clock-screenshot.jpg`; do not capture authenticated household data.

Then run `bash scripts/render-docs-hero.sh` with ImageMagick 7. The script adds
only perspective and shadow, and refuses a source with different dimensions
until its layout has been reviewed. The README links to the unchanged flat
screenshot for readability.
