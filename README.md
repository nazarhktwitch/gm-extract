# gm-extract

CLI tool for extracting GameMaker assets from data.win files.

## What it extracts

- Sprites, one PNG per frame, cut using the Texture Page Item (TPAG) rectangles
- Tilesets, as a whole image and as individual tiles
- Fonts, as a whole image and as individual glyphs
- Audio from the embedded AUDO chunk and from external audio groups (`*.dat`)
- All strings (`strings.txt`)
- A `manifest.json` listing every extracted resource, plus object, room, script, shader, timeline and sequence names

Texture pages in PNG, BZ2 + QOI (`2zoq`) and plain QOI (`fioq`) formats are supported.

## Requirements

Python 3.8 or newer.

## Installation from PyPI

```bash
pip install gm-extract
```

## Installation from source

```bash
git clone https://github.com/nazarhktwitch/gm-extract
cd gm-extract
pip install .
```

Or run without installing:

```bash
PYTHONPATH=src python -m gm_extract
```

## Usage

```bash
gm-extract path/to/data.win
gm-extract path/to/data.win -o output_dir
gm-extract --list path/to/data.win
```

If no path is given, `data.win` (or a single `*.win` / `*.unx` file) in the current directory is used.

External audio groups are looked up next to `data.win`.

### Options

| Option | Description |
| --- | --- |
| `-o`, `--out DIR` | Output directory. Default: `extracted` |
| `--list` | Print the contents and exit without writing files |
| `--pages` | Also save whole texture pages |
| `--sheets` | Also save each animation as a single `sheet.png` |
| `--pad` | Place frames on a canvas of the sprite size, keeping transparent margins |
| `--no-sprites` | Skip sprites |
| `--no-tilesets` | Skip tilesets |
| `--no-fonts` | Skip fonts |
| `--no-audio` | Skip audio |
| `--no-strings` | Skip strings |

## Limitations

- The texture table layout used by GameMaker 2022.9 and later is assumed. Older `data.win` files are not supported. For older versions check [Related projects](#related-projects) (e.g. GMS Explorer for GMS 1)
- Textures stored outside `data.win` are skipped with a warning.
- `--sheets` only includes frames that are on the same texture page as the first frame of the sprite.
- Only sprites of the normal type are extracted. Spine and SWF sprites are not.

## Related projects

- [GMExtract](https://github.com/puggsoy/GMExtract): extracts sprites and audio from the `data.win` of Game Maker Studio games. No longer maintained; its README names GMS Explorer as the successor.
- [GMS Explorer](https://github.com/puggsoy/GMS-Explorer): opens and browses `data.win`, extracts the frames of a sprite. On hiatus. Supports only GMS 1.

## License

MIT. See [LICENSE](LICENSE).
