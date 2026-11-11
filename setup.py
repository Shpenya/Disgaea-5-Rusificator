"""Русификатор Disgaea 5: добавляет мод "Russian" в D5 Mod Kit (запускается из Установить.bat Python'ом самого кита).

    python setup.py [папка D5 Mod Kit]

Кит не знает про русские буквы, поэтому кроме самого мода в кит кладётся его обработчик (d5lib/ruspatch.py: ширины
букв в exe, тексты базы, имена) и две маленькие правки. Повторный запуск ничего не ломает: после обновления кита
просто запустите Установить.bat ещё раз.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = "Russian"


def main():
    kit = os.path.abspath(sys.argv[1].strip().strip('"')) if len(sys.argv) > 1 else os.path.dirname(HERE)
    lib = os.path.join(kit, "d5lib")
    if not os.path.isfile(os.path.join(lib, "modsys.py")):
        sys.exit(f"Не нашёл D5 Mod Kit в папке: {kit}\nУкажите папку, где лежит «Start D5 Mod Kit.bat».")

    # 1. обработчик мода
    shutil.copy2(os.path.join(HERE, "kit", "ruspatch.py"), os.path.join(lib, "ruspatch.py"))

    # 2. регистрация обработчика (после outfits: его финализатор пересобирает exe из оригинала)
    p = os.path.join(lib, "modsys.py")
    t = read(p)
    if '"d5lib.ruspatch"' not in t:
        new = t.replace('"d5lib.unlockpatch"', '"d5lib.ruspatch", "d5lib.unlockpatch"', 1)
        if new == t:
            new = re.sub(r'(HANDLER_MODULES\s*=\s*\[[^\]]*)\]', r'\1, "d5lib.ruspatch"]', t, count=1)
        if new == t:
            sys.exit("Эта версия D5 Mod Kit не похожа на поддерживаемую (нет HANDLER_MODULES в d5lib/modsys.py).")
        write(p, new)

    # 3. перевод имён персонажей не должен снимать сюжетные блокировки навыков (unlockpatch считает такие строки
    #    char.dat «изменёнными модом»): при сравнении языковые поля не учитываются
    p = os.path.join(lib, "unlockpatch.py")
    if os.path.isfile(p):
        t = read(p)
        if "def modded_classes" in t and "f.lang and f.type ==" not in t:
            new = re.sub(r"def modded_classes\(.*?(?=\n\n\n|\Z)", MODDED_CLASSES, t, count=1, flags=re.S)
            write(p, new)

    # 4. сам мод
    dst = os.path.join(kit, "mods", MOD)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(HERE, MOD), dst)

    # 5. включить в активном профиле, последним (его тексты ложатся поверх остальных модов)
    sys.path.insert(0, kit)
    from d5lib.modsys import ModManager
    mm = ModManager(kit)
    order = [m for m in mm.load_order() if m != MOD] + [MOD]
    mm.save_load_order(order)

    print("Готово: мод «Russian» добавлен в D5 Mod Kit и включён.")
    print("Дальше: запустите «Start D5 Mod Kit.bat» и нажмите «Install & Play».")
    print("Язык игры должен быть английский (English).")


MODDED_CLASSES = '''def modded_classes(char_table, vanilla_table):
    """ids of the char.dat rows mods added or changed (a translation -- only the language text slots changed --
    doesn't count: it must not lift the story locks)"""
    texts = [f for f in char_table.schema.fields if f.lang and f.type == "str"]

    def key(r):
        b = bytearray(r.raw)
        for f in texts:
            b[f.offset:f.end] = bytes(f.size)
        return bytes(b)
    van = {r["id"]: key(r) for r in vanilla_table.rows}
    return sorted(r["id"] for r in char_table.rows if van.get(r["id"]) != key(r))'''


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, t):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)


if __name__ == "__main__":
    main()
