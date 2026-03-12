# Icon Assets for JAFO Remote

Place your branding icon files in this directory before building.

## Required Files

| Filename           | Format | Dimensions                      | Used For                              |
|--------------------|--------|---------------------------------|---------------------------------------|
| `logo.svg`         | SVG    | Vector (no fixed size)          | In-app Flutter logo                   |
| `icon-1024.png`    | PNG    | 1024x1024                       | macOS app icon (generates all sizes)  |
| `icon-512.png`     | PNG    | 512x512                         | Linux packaging                       |
| `icon-128.png`     | PNG    | 128x128                         | Linux tray, res/ directory            |
| `icon-32.png`      | PNG    | 32x32                           | Small UI contexts, res/ directory     |
| `icon-windows.ico` | ICO    | Multi-res (16,32,48,64,128,256) | Windows taskbar and installer         |

## How to Generate

Start with a **1024x1024 PNG** master image (`icon-1024.png`), then generate the rest:

```bash
# Install ImageMagick if needed
# Ubuntu: sudo apt install imagemagick
# macOS: brew install imagemagick

# Generate PNG sizes from master
convert icon-1024.png -resize 512x512 icon-512.png
convert icon-1024.png -resize 128x128 icon-128.png
convert icon-1024.png -resize 32x32 icon-32.png

# Generate Windows .ico (contains multiple resolutions)
convert icon-1024.png \
  \( -clone 0 -resize 16x16 \) \
  \( -clone 0 -resize 32x32 \) \
  \( -clone 0 -resize 48x48 \) \
  \( -clone 0 -resize 64x64 \) \
  \( -clone 0 -resize 128x128 \) \
  \( -clone 0 -resize 256x256 \) \
  -delete 0 icon-windows.ico
```

## Notes

- The ICO file must contain multiple embedded resolutions (16, 32, 48, 64, 128, 256) for proper Windows display at all sizes.
- The SVG logo should be clean vector art (not a rasterized embed) for best rendering in the Flutter UI.
- Use a transparent background for all PNG files.
- The `apply-branding.py` script will warn but continue if any files are missing.
