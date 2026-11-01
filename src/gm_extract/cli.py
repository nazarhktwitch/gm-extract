import argparse
import logging
import os
import sys

from . import __version__
from .extractor import Options, extract, load_catalog
from .gamedata import GameData

DATA_EXTENSIONS = (".win", ".unx")

def _configure_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

def build_parser():
    ap = argparse.ArgumentParser(
        prog="gm-extract",
        description="Extract sprites, tilesets, fonts, audio and strings from GameMaker data.win files.",
    )
    ap.add_argument("data", nargs="?", help="path to data.win (default: look in the current directory)")
    ap.add_argument("-o", "--out", default="extracted", help="output directory (default: extracted)")
    ap.add_argument("--list", action="store_true", help="print the contents and exit without writing files")
    ap.add_argument("--pages", action="store_true", help="also save whole texture pages")
    ap.add_argument("--sheets", action="store_true", help="also save each animation as a single sheet.png")
    ap.add_argument("--pad", action="store_true",
                    help="place frames on a canvas of the sprite size, keeping transparent margins")
    ap.add_argument("--no-sprites", action="store_true")
    ap.add_argument("--no-tilesets", action="store_true")
    ap.add_argument("--no-fonts", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-strings", action="store_true")
    ap.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    return ap

def find_data_file(explicit):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    cwd = os.getcwd()
    default = os.path.join(cwd, "data.win")
    if os.path.isfile(default):
        return default
    candidates = [f for f in os.listdir(cwd) if f.lower().endswith(DATA_EXTENSIONS)]
    if len(candidates) == 1:
        return os.path.join(cwd, candidates[0])
    return None

def print_listing(catalog):
    print("\n--- Sprites ---")
    for s in catalog.sprites:
        print(f"  {s['name'] or '<unnamed>':<40} {s['width']:>4}x{s['height']:<4} frames: {len(s['textures'])}")
    print("\n--- Tilesets ---")
    for ts in catalog.tilesets:
        print(f"  {ts['name'] or '<unnamed>'} (tile {ts['tile_w']}x{ts['tile_h']}, columns {ts['columns']})")
    print("\n--- Fonts ---")
    for font in catalog.fonts:
        print(f"  {font['name'] or '<unnamed>'} ({len(font['glyphs'])} glyphs)")
    print("\n--- Sounds ---")
    for s in catalog.sounds:
        print(f"  [{s['group']}/{s['audio_id']}] {s['name']}")

def main(argv=None):
    _configure_streams()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)

    data_path = find_data_file(args.data)
    if data_path is None:
        print("data.win not found. Pass its path as an argument.", file=sys.stderr)
        return 1

    logging.info("Reading %s ...", data_path)
    try:
        g = GameData(data_path)
        catalog = load_catalog(g)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    logging.info("Game: %s | bytecode %d | chunks: %d", g.game_name or "?", g.bytecode, len(g.chunks))
    logging.info("Sprites: %d, tilesets: %d, fonts: %d, sounds: %d, audio groups: %d",
                 len(catalog.sprites), len(catalog.tilesets), len(catalog.fonts),
                 len(catalog.sounds), len(catalog.audio_groups))
    logging.info("Texture pages: %d, strings: %d", len(g.textures), len(g.strings))

    if args.list:
        print_listing(catalog)
        return 0

    opts = Options(
        out_dir=os.path.abspath(args.out),
        pages=args.pages,
        sheets=args.sheets,
        pad=args.pad,
        sprites=not args.no_sprites,
        tilesets=not args.no_tilesets,
        fonts=not args.no_fonts,
        audio=not args.no_audio,
        strings=not args.no_strings,
    )
    extract(g, catalog, opts)
    return 0
