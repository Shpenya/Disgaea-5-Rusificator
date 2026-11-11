"""Russian letters for disgaea5.exe: advance widths of U+0500..U+055F.

The Russian localization writes its letters as U+0500..U+055F (Cyrillic + 0x100: the game uses many real Cyrillic
code points as inline icon codes) and gives the font's 66 Cyrillic glyphs those codes (font.ffm, see the mod's
build script).  The game's glyph width function (0x1402c8110) gives every code outside ASCII / Latin-1 a fixed
full width; this hook returns a proportional width for them instead.

The width function is called with a 2-byte code either right-aligned (0x0000D4B1) or left-aligned (0xD4B10000);
both are handled.  Codes without a width in the table keep the game's behaviour.

Stored in a mod as patches/russian/widths.json: {"а": 16, "б": 17, ...} (keys: normal Cyrillic letters U+0400..U+045F,
values: advance in the units the width function returns, i.e. like round(ascii_table * 0.67)).
"""
from . import exepatch
from .gamefs import EXE_FILE
from .modsys import register_finalizer, register_patch_handler

FOLDER = "russian"
SECTION = b".d5ru"
WIDTH_ORIG = bytes.fromhex("4883ec28448bc1")      # sub rsp, 0x28 / mov r8d, ecx
# the width function's start (0x1402c8110 in the Steam build 9460a6411699): found by its bytes, so the patch needs
# no address map; it ends with `cmp ecx, 0x20 / je` and the left-aligned-space test
WIDTH_SIG = bytes.fromhex("4883ec28448bc183f9200f84")


def _find_width_fn(exe: bytes) -> int:
    import pefile
    pe = pefile.PE(data=exe, fast_load=True)
    text = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
    body = exe[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
    hits = []
    i = body.find(WIDTH_SIG)
    while i >= 0:
        # the same function also compares with 0x2000, 0x200000 and 0x20000000 (the four forms of a space)
        if b"\x00\x20\x00\x00" in body[i:i + 64] and b"\x00\x00\x00\x20" in body[i:i + 64]:
            hits.append(i)
        i = body.find(WIDTH_SIG, i + 1)
    if len(hits) != 1:
        raise ValueError(f"unexpected exe version: glyph width function found {len(hits)} times")
    return exepatch.IMAGE_BASE + text.VirtualAddress + hits[0]


def build_width_patch(exe: bytes, widths: dict) -> bytes:
    from . import exemap
    va = _find_width_fn(exe)
    ret = va + len(WIDTH_ORIG)
    tbl = [0] * 0x60
    for ch, w in widths.items():
        i = ord(ch) - 0x400
        if 0 <= i < 0x60:
            tbl[i] = max(1, min(255, int(w)))
    src = "\n".join([
        "    mov eax, ecx",
        "    cmp eax, 0xffff",
        "    jbe ru_code",
        "    test eax, 0xffff",            # left-aligned 2-byte code: low half empty
        "    jne ru_orig",
        "    shr eax, 16",
        "ru_code:",
        "    lea edx, [rax - 0xd480]",      # U+0500..U+053F = d4 80..d4 bf -> 0..63
        "    cmp edx, 0x3f",
        "    jbe ru_hit",
        "    lea edx, [rax - 0xd580]",      # U+0540..U+055F = d5 80..d5 9f -> 64..95
        "    cmp edx, 0x1f",
        "    ja ru_orig",
        "    add edx, 0x40",
        "ru_hit:",
        "    lea rax, [rip + ru_tbl]",
        "    movzx eax, byte ptr [rax + rdx]",
        "    test eax, eax",
        "    je ru_orig",
        "    ret",
        "ru_orig:",
        "    sub rsp, 0x28",
        "    mov r8d, ecx",
        f"    jmp {ret:#x}",
        "ru_tbl:",
        "    .byte " + ", ".join(map(str, tbl)),
    ])
    # the site was found in THIS exe: assemble without the kit's known-build address translation
    saved = exemap.ACTIVE
    exemap.use(exemap.Translator(saved.sha1))
    try:
        return exepatch.add_hook_section(exe, SECTION, [(va, WIDTH_ORIG, src, 0xE9)])
    finally:
        exemap.use(saved)


def apply_texts(ctx, texts):
    """texts.json: {table member: {row index: {text field: value}}} -- only language text fields are written (unlike
    the "db" handler, nothing else of the row is touched, so story locks / evility counts stay the game's own)"""
    from . import database
    from .dbpatch import DB_ARCHIVE
    n = skipped = 0
    for member, rows in texts.items():
        vpath = f"{DB_ARCHIVE}/{member}"
        table = database.load_table(member, ctx.get(vpath))
        vanilla = database.load_table(member, ctx.fs.read(vpath)).rows
        # name.dat (random names): its one text field has no language tag
        fields = {f.name: f for f in table.schema.fields
                  if (f.lang or member.lower() == "name.dat") and f.type in ("str", "strptr")}
        for ri, vals in rows.items():
            for name, value in vals.items():
                f = fields.get(name)
                # texts are for the vanilla rows: a row another mod changed (or moved) keeps that mod's text
                if f is None or int(ri) >= min(len(table.rows), len(vanilla)) \
                        or table.rows[int(ri)][name] != vanilla[int(ri)][name]:
                    skipped += 1
                    continue
                if f.type == "str" and len(value.encode("utf-8")) > f.size - 1:
                    skipped += 1
                    continue
                table.rows[int(ri)][name] = value
                n += 1
        ctx.put(vpath, table.to_bytes())
    ctx.log(f"  Russian texts: {n} database texts" + (f", {skipped} left out (too long / unknown)" if skipped else ""))


def _handler(ctx, mod, patch_dir):
    widths = {}
    for fname in mod.list_patches(FOLDER):
        if fname.lower() == "widths.json":
            widths.update(mod.load_patch(FOLDER, fname) or {})
        elif fname.lower() == "texts.json":
            apply_texts(ctx, mod.load_patch(FOLDER, fname) or {})
    if widths:
        # applied by the finalizer: the outfits finalizer rebuilds the exe from the vanilla one
        ctx._ru_widths = {**getattr(ctx, "_ru_widths", {}), **widths}


def _finalize(ctx):
    widths = getattr(ctx, "_ru_widths", None)
    if widths:
        ctx.put(EXE_FILE, build_width_patch(ctx.get(EXE_FILE), widths))
        ctx.log(f"  Russian letters: widths of {len(widths)} glyphs")


register_patch_handler(FOLDER, _handler, order=60)
register_finalizer(_finalize)
