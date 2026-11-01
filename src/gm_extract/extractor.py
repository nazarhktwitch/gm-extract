import json
import logging
import os
import time
from collections import namedtuple
from dataclasses import dataclass

from .audio import (
    audio_ext,
    parse_audio_groups,
    parse_sounds,
    read_audiogroup_file,
    read_embedded_audio,
)
from .names import safe_name, unique_name
from .png import crop_rgba, place_on_canvas, write_png
from .resources import parse_backgrounds, parse_fonts, parse_sprites

log = logging.getLogger(__name__)

NAMED_CHUNKS = ("OBJT", "ROOM", "SCPT", "SHDR", "TMLN", "SEQN")

Page = namedtuple("Page", "index width height rgba")

@dataclass
class Options:
    out_dir: str
    pages: bool = False
    sheets: bool = False
    pad: bool = False
    sprites: bool = True
    tilesets: bool = True
    fonts: bool = True
    audio: bool = True
    strings: bool = True

@dataclass
class Catalog:
    sprites: list
    tilesets: list
    fonts: list
    audio_groups: list
    sounds: list
    names: dict

def load_catalog(g):
    return Catalog(
        sprites=parse_sprites(g),
        tilesets=parse_backgrounds(g),
        fonts=parse_fonts(g),
        audio_groups=parse_audio_groups(g),
        sounds=parse_sounds(g),
        names={chunk: g.resource_names(chunk) for chunk in NAMED_CHUNKS if g.has(chunk)},
    )

def extract(g, catalog, opts):
    started = time.time()
    os.makedirs(opts.out_dir, exist_ok=True)

    manifest = {
        "game": g.game_name,
        "bytecode": g.bytecode,
        "data_win": os.path.basename(g.path),
        "sprites": [], "tilesets": [], "fonts": [], "sounds": [],
        "audio_groups": catalog.audio_groups,
        "objects": catalog.names.get("OBJT", []),
        "rooms": catalog.names.get("ROOM", []),
        "scripts": catalog.names.get("SCPT", []),
        "shaders": catalog.names.get("SHDR", []),
        "timelines": catalog.names.get("TMLN", []),
        "sequences": catalog.names.get("SEQN", []),
    }

    jobs = {}
    if opts.sprites:
        _plan_sprites(g, catalog.sprites, opts, manifest, jobs)
    if opts.tilesets:
        _plan_tilesets(g, catalog.tilesets, opts, manifest, jobs)
    if opts.fonts:
        _plan_fonts(g, catalog.fonts, opts, manifest, jobs)

    _run_jobs(g, jobs, opts, started)

    if opts.audio and catalog.sounds:
        _extract_audio(g, catalog, opts, manifest)
    if opts.strings and g.strings:
        _write_strings(g, opts)

    with open(os.path.join(opts.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    log.info("Done in %.1f s", time.time() - started)
    log.info("Output: %s", opts.out_dir)
    log.info("  sprites: %d | tilesets: %d | fonts: %d | sounds: %d",
             len(manifest["sprites"]), len(manifest["tilesets"]),
             len(manifest["fonts"]), len(manifest["sounds"]))
    return manifest

def _add_job(jobs, page, job):
    jobs.setdefault(page, []).append(job)

def _plan_sprites(g, sprites, opts, manifest, jobs):
    used = set()
    for s in sprites:
        name = unique_name(safe_name(s["name"], f"sprite_{s['index']}"), used)
        frames = []
        for index, tpag_ptr in enumerate(s["textures"]):
            t = g.tpag(tpag_ptr)
            if not t:
                continue
            src_x, src_y, src_w, src_h, dst_x, dst_y = t[:6]
            page = t[10]
            if page >= len(g.textures):
                continue
            rel = f"sprites/{name}/frame_{index}.png"
            frames.append({
                "page": page, "x": src_x, "y": src_y, "w": src_w, "h": src_h,
                "dst_x": dst_x, "dst_y": dst_y,
                "canvas_w": s["width"], "canvas_h": s["height"],
                "file": rel,
            })
            job = {
                "kind": "img", "path": os.path.join(opts.out_dir, rel),
                "x": src_x, "y": src_y, "w": src_w, "h": src_h,
            }
            if opts.pad:
                job["canvas"] = (s["width"], s["height"], dst_x, dst_y)
            _add_job(jobs, page, job)

        if not frames:
            continue
        if opts.sheets and len(frames) > 1:
            _add_job(jobs, frames[0]["page"], {
                "kind": "sheet",
                "path": os.path.join(opts.out_dir, "sprites", name, "sheet.png"),
                "frames": frames, "pad": opts.pad,
            })
        manifest["sprites"].append({
            "name": s["name"], "width": s["width"], "height": s["height"],
            "origin_x": s["origin_x"], "origin_y": s["origin_y"],
            "frames": frames,
        })

def _plan_tilesets(g, tilesets, opts, manifest, jobs):
    used = set()
    for ts in tilesets:
        t = g.tpag(ts["tex_ptr"])
        if not t:
            continue
        src_x, src_y, src_w, src_h = t[:4]
        page = t[10]
        if page >= len(g.textures):
            continue
        name = unique_name(safe_name(ts["name"], f"tileset_{ts['index']}"), used)
        rel = f"tilesets/{name}.png"
        _add_job(jobs, page, {
            "kind": "img", "path": os.path.join(opts.out_dir, rel),
            "x": src_x, "y": src_y, "w": src_w, "h": src_h,
        })
        _add_job(jobs, page, {
            "kind": "tiles",
            "dir": os.path.join(opts.out_dir, "tilesets", f"{name}_tiles"),
            "rect": (src_x, src_y),
            "tile_w": ts["tile_w"], "tile_h": ts["tile_h"],
            "border_x": ts["border_x"], "border_y": ts["border_y"],
            "columns": ts["columns"], "count": ts["tile_count"],
        })
        manifest["tilesets"].append({
            "name": ts["name"],
            "tile_width": ts["tile_w"], "tile_height": ts["tile_h"],
            "columns": ts["columns"], "tile_count": ts["tile_count"],
            "file": rel,
        })

def _plan_fonts(g, fonts, opts, manifest, jobs):
    used = set()
    for font in fonts:
        t = g.tpag(font["tex_ptr"])
        if not t:
            continue
        src_x, src_y, src_w, src_h = t[:4]
        page = t[10]
        if page >= len(g.textures):
            continue
        name = unique_name(safe_name(font["name"], f"font_{font['index']}"), used)
        rel = f"fonts/{name}.png"
        _add_job(jobs, page, {
            "kind": "img", "path": os.path.join(opts.out_dir, rel),
            "x": src_x, "y": src_y, "w": src_w, "h": src_h,
        })
        if font["glyphs"]:
            _add_job(jobs, page, {
                "kind": "glyphs",
                "dir": os.path.join(opts.out_dir, "fonts", f"{name}_glyphs"),
                "rect": (src_x, src_y),
                "glyphs": font["glyphs"],
            })
        manifest["fonts"].append({
            "name": font["name"], "display_name": font["display_name"],
            "glyphs": len(font["glyphs"]), "file": rel,
        })

def _save(path, width, height, rgba):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_png(path, width, height, rgba)

def _write_image(job, page):
    data, w, h = crop_rgba(page.rgba, page.width, page.height,
                           job["x"], job["y"], job["w"], job["h"])
    if job.get("canvas"):
        data, w, h = place_on_canvas(data, w, h, *job["canvas"])
    _save(job["path"], w, h, data)

def _write_sheet(job, page):
    parts = []
    total_w = max_h = 0
    for fr in job["frames"]:
        if fr["page"] != page.index:
            continue
        data, w, h = crop_rgba(page.rgba, page.width, page.height,
                               fr["x"], fr["y"], fr["w"], fr["h"])
        if job["pad"]:
            data, w, h = place_on_canvas(data, w, h, fr["canvas_w"], fr["canvas_h"],
                                         fr["dst_x"], fr["dst_y"])
        parts.append((data, w, h))
        total_w += w
        max_h = max(max_h, h)

    if not parts:
        return
    sheet = bytearray(total_w * max_h * 4)
    x_offset = 0
    for data, w, h in parts:
        for row in range(h):
            start = (row * total_w + x_offset) * 4
            sheet[start:start + w * 4] = data[row * w * 4:(row + 1) * w * 4]
        x_offset += w
    _save(job["path"], total_w, max_h, bytes(sheet))

def _write_tiles(job, page):
    rx, ry = job["rect"]
    tw, th = job["tile_w"], job["tile_h"]
    step_x = tw + 2 * job["border_x"]
    step_y = th + 2 * job["border_y"]
    columns = max(1, job["columns"])
    os.makedirs(job["dir"], exist_ok=True)
    for i in range(job["count"]):
        col = i % columns
        row = i // columns
        data, w, h = crop_rgba(page.rgba, page.width, page.height,
                               rx + col * step_x + job["border_x"],
                               ry + row * step_y + job["border_y"], tw, th)
        write_png(os.path.join(job["dir"], f"tile_{i:04d}.png"), w, h, data)

def _write_glyphs(job, page):
    rx, ry = job["rect"]
    os.makedirs(job["dir"], exist_ok=True)
    seen = set()
    for gl in job["glyphs"]:
        char = gl["char"]
        if char in seen or not gl["w"] or not gl["h"]:
            continue
        seen.add(char)
        data, w, h = crop_rgba(page.rgba, page.width, page.height,
                               rx + gl["x"], ry + gl["y"], gl["w"], gl["h"])
        write_png(os.path.join(job["dir"], f"U+{char:04X}.png"), w, h, data)

_HANDLERS = {
    "img": _write_image,
    "sheet": _write_sheet,
    "tiles": _write_tiles,
    "glyphs": _write_glyphs,
}

def _run_jobs(g, jobs, opts, started):
    pages = set(jobs)
    if opts.pages:
        pages |= set(range(len(g.textures)))

    done = 0
    for index in sorted(pages):
        try:
            width, height, rgba = g.decode_page(index)
        except Exception as e:
            log.warning("page %d: %s", index, e)
            continue
        page = Page(index, width, height, rgba)

        if opts.pages:
            pages_dir = os.path.join(opts.out_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)
            write_png(os.path.join(pages_dir, f"page_{index:02d}.png"), width, height, rgba)

        for job in jobs.get(index, []):
            try:
                _HANDLERS[job["kind"]](job, page)
            except Exception as e:
                log.warning("%s: %s", job.get("path") or job.get("dir"), e)

        done += 1
        log.info("  page %d/%d done (%.1f s)", done, len(pages), time.time() - started)

def _load_audio_group(g, group, group_id):
    if group_id == 0:
        try:
            return read_embedded_audio(g)
        except Exception as e:
            log.warning("embedded AUDO: %s", e)
            return []

    if not group:
        return []
    filename = group["file"]
    path = os.path.join(g.dir, filename.replace("\\", os.sep).replace("/", os.sep))
    if not os.path.isfile(path):
        wanted = os.path.basename(filename).lower()
        matches = [f for f in os.listdir(g.dir) if f.lower() == wanted]
        if matches:
            path = os.path.join(g.dir, matches[0])
    if not os.path.isfile(path):
        log.warning("audio group file not found: %s", path)
        return []
    try:
        return read_audiogroup_file(path)
    except Exception as e:
        log.warning("%s: %s", path, e)
        return []

def _extract_audio(g, catalog, opts, manifest):
    groups = catalog.audio_groups
    by_group = {}
    for s in catalog.sounds:
        by_group.setdefault(s["group"], []).append(s)

    used_files = set()
    for group_id, items in sorted(by_group.items()):
        group = groups[group_id] if 0 <= group_id < len(groups) else None
        group_name = group["name"] if group else f"group_{group_id}"
        group_dir_name = safe_name(group_name, f"group_{group_id}")
        group_dir = os.path.join(opts.out_dir, "audio", group_dir_name)
        os.makedirs(group_dir, exist_ok=True)

        blobs = _load_audio_group(g, group, group_id)
        for s in items:
            audio_id = s["audio_id"]
            if not 0 <= audio_id < len(blobs) or not blobs[audio_id]:
                continue
            raw = blobs[audio_id]
            base = safe_name(s["name"], f"{group_name}_{audio_id}")
            filename = unique_name(base, used_files, "." + audio_ext(raw))
            with open(os.path.join(group_dir, filename), "wb") as f:
                f.write(raw)
            manifest["sounds"].append({
                "name": s["name"], "group": group_name, "audio_id": audio_id,
                "file": f"audio/{group_dir_name}/{filename}", "size": len(raw),
            })
    log.info("  sounds: %d", len(manifest["sounds"]))

def _write_strings(g, opts):
    path = os.path.join(opts.out_dir, "strings.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for s in g.strings:
            f.write(s.replace("\r", "\\r").replace("\n", "\\n") + "\n")
