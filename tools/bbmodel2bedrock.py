"""แปลง .bbmodel (Blockbench/Model Engine) -> Bedrock addon files

ทำตามสูตรเดียวกับ Blockbench bedrock codec:
- cube:  origin_x = -(from_x + size_x), pivot_x *= -1, rotation x/y กลับเครื่องหมาย
- face uv: uv=[u1,v1], uv_size=[u2-u1, v2-v1]; หน้า up/down พลิก (uv+=size, size*=-1)
- bone:  pivot_x *= -1, rotation x/y กลับเครื่องหมาย
- anim:  position x กลับเครื่องหมาย, rotation x/y กลับเครื่องหมาย
"""
import base64
import glob
import json
import os
import re
import sys

# กัน UnicodeEncodeError เวลา path มีภาษาไทยแล้วคอนโซลเป็น cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# รันเปล่า ๆ ได้เลย: หาโฟลเดอร์อัตโนมัติจากตำแหน่งสคริปต์ (tools/ อยู่ในโปรเจกต์)
# หรือระบุเอง: py bbmodel2bedrock.py <โฟลเดอร์ bbmodel> <NPCPack_RP> <NPCPack_BP>
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_ROOT, "java_npc", "blueprints")
RP_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_ROOT, "addon", "NPCPack_RP")
BP_DIR = sys.argv[3] if len(sys.argv) > 3 else os.path.join(_ROOT, "addon", "NPCPack_BP")

for _p, _label in ((SRC_DIR, "bbmodel folder"), (RP_DIR, "NPCPack_RP"), (BP_DIR, "NPCPack_BP")):
    if not os.path.isdir(_p):
        print(f"ERROR: not found {_label}: {_p}")
        print("usage: py bbmodel2bedrock.py [bbmodel_folder] [NPCPack_RP] [NPCPack_BP]")
        sys.exit(1)
print("source :", SRC_DIR)
print("RP     :", RP_DIR)
print("BP     :", BP_DIR)

BP_TEMPLATE = json.load(open(os.path.join(BP_DIR, "entities", "npc.json"), encoding="utf-8-sig"))


def slug(name):
    s = re.sub(r"[^a-z0-9_]", "_", name.lower())
    return re.sub(r"_+", "_", s).strip("_")


def num(v):
    try:
        f = float(v)
        return round(f, 4)
    except (TypeError, ValueError):
        return v  # molang string


def invert(v):
    v = num(v)
    if isinstance(v, str):
        return v if v.strip() in ("0", "") else f"-({v})"
    return -v if v != 0 else 0


def timecode(t):
    return f"{round(float(t), 4):g}"


def convert_model(path):
    j = json.load(open(path, encoding="utf-8-sig"))
    name = slug(os.path.splitext(os.path.basename(path))[0])
    res = j.get("resolution", {})
    tex_w, tex_h = res.get("width", 64), res.get("height", 64)

    elements = {e["uuid"]: e for e in j.get("elements", []) if e.get("type", "cube") == "cube"}

    used_names = {}

    def unique(n):
        n = slug(n) or "bone"
        if n in used_names:
            used_names[n] += 1
            return f"{n}_{used_names[n]}"
        used_names[n] = 1
        return n

    bones = []
    name_map = {}  # ชื่อ group เดิม -> ชื่อ bone สุดท้าย
    min_y, max_y, max_r = 0.0, 16.0, 8.0

    def conv_cube(e):
        nonlocal min_y, max_y, max_r
        fx, fy, fz = e["from"]
        tx, ty, tz = e["to"]
        size = [round(tx - fx, 4), round(ty - fy, 4), round(tz - fz, 4)]
        cube = {"origin": [round(-(fx + size[0]), 4), round(fy, 4), round(fz, 4)], "size": size}
        min_y, max_y = min(min_y, fy), max(max_y, ty)
        max_r = max(max_r, abs(fx), abs(tx), abs(fz), abs(tz))
        if e.get("inflate"):
            cube["inflate"] = e["inflate"]
        rot = e.get("rotation")
        if rot and any(rot):
            ox, oy, oz = e.get("origin", [0, 0, 0])
            cube["pivot"] = [round(-ox, 4), round(oy, 4), round(oz, 4)]
            cube["rotation"] = [round(-rot[0], 4), round(-rot[1], 4), round(rot[2], 4)]
        uv = {}
        for face, fd in e.get("faces", {}).items():
            if fd.get("texture") is None:
                continue
            u1, v1, u2, v2 = fd["uv"]
            fuv = [round(u1, 4), round(v1, 4)]
            fsz = [round(u2 - u1, 4), round(v2 - v1, 4)]
            if face in ("up", "down"):
                fuv = [round(fuv[0] + fsz[0], 4), round(fuv[1] + fsz[1], 4)]
                fsz = [-fsz[0], -fsz[1]]
            uv[face] = {"uv": fuv, "uv_size": fsz}
        cube["uv"] = uv
        return cube

    def walk(node, parent):
        if isinstance(node, str):
            return  # cube uuid จัดการที่ชั้น parent แล้ว
        raw = node.get("name", "bone")
        if slug(raw) == "hitbox":
            return  # bone hitbox ของ Model Engine ไม่ใช่ส่วนแสดงผล
        bname = unique(raw)
        name_map.setdefault(raw, bname)
        ox, oy, oz = node.get("origin", [0, 0, 0])
        bone = {"name": bname, "pivot": [round(-ox, 4), round(oy, 4), round(oz, 4)]}
        if parent:
            bone["parent"] = parent
        rot = node.get("rotation")
        if rot and any(rot):
            bone["rotation"] = [round(-rot[0], 4), round(-rot[1], 4), round(rot[2], 4)]
        cubes = [conv_cube(elements[c]) for c in node.get("children", [])
                 if isinstance(c, str) and c in elements
                 and elements[c].get("visibility", True) and elements[c].get("export", True)]
        if cubes:
            bone["cubes"] = cubes
        bones.append(bone)
        for c in node.get("children", []):
            if isinstance(c, dict):
                walk(c, bname)

    root_cubes = []
    for node in j.get("outliner", []):
        if isinstance(node, str):
            if node in elements:
                root_cubes.append(conv_cube(elements[node]))
        else:
            walk(node, None)
    if root_cubes:
        bones.append({"name": "bb_root", "pivot": [0, 0, 0], "cubes": root_cubes})

    geo = {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": f"geometry.npcp_{name}",
                "texture_width": tex_w,
                "texture_height": tex_h,
                "visible_bounds_width": round(max_r / 16 * 2 + 1, 1),
                "visible_bounds_height": round((max_y - min_y) / 16 + 0.5, 1),
                "visible_bounds_offset": [0, round((max_y + min_y) / 32, 2), 0],
            },
            "bones": bones,
        }],
    }
    os.makedirs(os.path.join(RP_DIR, "models", "entity"), exist_ok=True)
    with open(os.path.join(RP_DIR, "models", "entity", f"{name}.geo.json"), "w", encoding="utf-8") as f:
        json.dump(geo, f, indent=1)

    # ---- texture (base64 ฝังใน bbmodel) ----
    textures = j.get("textures", [])
    n_tex = len(textures)
    if textures:
        src = textures[0].get("source", "")
        b64 = src.split(",", 1)[1] if "," in src else ""
        os.makedirs(os.path.join(RP_DIR, "textures", "entity"), exist_ok=True)
        with open(os.path.join(RP_DIR, "textures", "entity", f"npcp_{name}.png"), "wb") as f:
            f.write(base64.b64decode(b64))

    # ---- animations ----
    anims = {}
    for a in j.get("animations", []):
        aname = slug(a.get("name", ""))
        if not aname:
            continue
        loop = a.get("loop", "once")
        tag = {"loop": True if loop == "loop" else ("hold_on_last_frame" if loop == "hold" else False)}
        if a.get("length"):
            tag["animation_length"] = round(a["length"], 4)
        bones_tag = {}
        for animator in a.get("animators", {}).values():
            if animator.get("type", "bone") != "bone":
                continue
            bname = name_map.get(animator.get("name", ""))
            if bname is None:
                continue
            channels = {}
            for kf in animator.get("keyframes", []):
                ch = kf.get("channel")
                if ch not in ("rotation", "position", "scale"):
                    continue
                dp = (kf.get("data_points") or [{}])[0]
                x, y, z = dp.get("x", 0), dp.get("y", 0), dp.get("z", 0)
                if ch == "rotation":
                    val = [invert(x), invert(y), num(z)]
                elif ch == "position":
                    val = [invert(x), num(y), num(z)]
                else:
                    val = [num(x), num(y), num(z)]
                channels.setdefault(ch, {})[timecode(kf.get("time", 0))] = val
            for ch, keys in channels.items():
                channels[ch] = dict(sorted(keys.items(), key=lambda kv: float(kv[0])))
            if channels:
                bones_tag[bname] = channels
        if bones_tag:
            anims[f"animation.npcp_{name}.{aname}"] = {**tag, "bones": bones_tag}
    if anims:
        os.makedirs(os.path.join(RP_DIR, "animations"), exist_ok=True)
        with open(os.path.join(RP_DIR, "animations", f"{name}.animation.json"), "w", encoding="utf-8") as f:
            json.dump({"format_version": "1.8.0", "animations": anims}, f, indent=1)

    # ---- client entity (RP) ----
    anim_names = [k.split(".")[-1] for k in anims]
    entity_anims = {a: f"animation.npcp_{name}.{a}" for a in anim_names}
    animate = ["idle"] if "idle" in anim_names else (anim_names[:1] if anim_names else [])
    client = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": f"npcp:{name}",
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": f"textures/entity/npcp_{name}"},
                "geometry": {"default": f"geometry.npcp_{name}"},
                "render_controllers": ["controller.render.npcp_npc"],
                **({"animations": entity_anims, "scripts": {"animate": animate}} if animate else {}),
            }
        },
    }
    with open(os.path.join(RP_DIR, "entity", f"{name}.entity.json"), "w", encoding="utf-8") as f:
        json.dump(client, f, indent=1)

    # ---- server entity (BP) — โครงเดียวกับ npcp:npc ----
    bp = json.loads(json.dumps(BP_TEMPLATE))
    bp["minecraft:entity"]["description"]["identifier"] = f"npcp:{name}"
    with open(os.path.join(BP_DIR, "entities", f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(bp, f, indent=1)

    return name, len(bones), n_tex, anim_names


results = []
for path in sorted(glob.glob(os.path.join(SRC_DIR, "**", "*.bbmodel"), recursive=True)):
    try:
        results.append(convert_model(path))
    except Exception as e:
        results.append((os.path.basename(path), "ERROR", str(e), []))

for r in results:
    print(r)
converted = [r[0] for r in results if r[1] != "ERROR"]
print(f"converted {len(converted)} models")

# ---------------------------------------------------------------
# ขั้นตอนอัตโนมัติหลังแปลง (ทำเฉพาะตอนรันในโครงสร้างโปรเจกต์ปกติ)
# ---------------------------------------------------------------

# 1) ลงทะเบียน type ใหม่เข้าปลั๊กอิน: อัปเดต src/endstone_npc/addon_types.json
#    (ปลั๊กอินอ่านไฟล์นี้ตอนโหลด — ไม่ต้องแก้โค้ดเอง)
types_file = os.path.join(_ROOT, "src", "endstone_npc", "addon_types.json")
if os.path.isfile(types_file):
    with open(types_file, encoding="utf-8") as f:
        existing = set(json.load(f))
    added = sorted(set(converted) - existing)
    merged = sorted(existing | set(converted))
    with open(types_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)
        f.write("\n")
    print(f"addon_types.json: +{len(added)} new {added if added else ''}")

    # 1.5) เจน npc_animations.json — สแกน animation ทั้งหมดใน RP
    #      ปลั๊กอินโหลดไฟล์นี้จาก data folder (plugins/NPCPlugin/)
    #      ไม่ต้อง rebuild wheel เมื่อเพิ่มโมเดลใหม่
    anim_map = {}
    anim_dir = os.path.join(RP_DIR, "animations")
    for anim_file in sorted(glob.glob(os.path.join(anim_dir, "*.animation.json"))):
        try:
            with open(anim_file, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        for full_name in data.get("animations", {}):
            parts = full_name.split(".")
            if len(parts) >= 3 and parts[0] == "animation" and parts[1].startswith("npcp_"):
                npc_type = parts[1][len("npcp_"):]
                action = ".".join(parts[2:])
                anim_map.setdefault(npc_type, []).append(action)
    anim_json = os.path.join(_ROOT, "npc_animations.json")
    with open(anim_json, "w", encoding="utf-8") as f:
        json.dump(anim_map, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"npc_animations.json: {len(anim_map)} types -> {anim_json}")

    # 2) repack addon/npc_pack.mcaddon (สำหรับแจกผู้เล่น)
    import zipfile
    mcaddon = os.path.join(_ROOT, "addon", "npc_pack.mcaddon")
    with zipfile.ZipFile(mcaddon, "w", zipfile.ZIP_DEFLATED) as z:
        for pack_dir in (BP_DIR, RP_DIR):
            base = os.path.basename(pack_dir)
            for root, _dirs, files in os.walk(pack_dir):
                for fn in files:
                    full = os.path.join(root, fn)
                    z.write(full, os.path.join(base, os.path.relpath(full, pack_dir)))
    print(f"repacked {mcaddon}")

    # 3) build wheel ใหม่ให้เลย (ถ้ามี pip)
    import subprocess
    dist = os.path.join(_ROOT, "dist")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", _ROOT, "--no-deps", "-w", dist],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        whls = sorted(glob.glob(os.path.join(dist, "*.whl")), key=os.path.getmtime)
        print(f"built wheel: {whls[-1] if whls else dist}")
        print("\nขั้นตอนต่อไป:")
        print("  1. copy addon/NPCPack_BP + NPCPack_RP ทับใน development packs ของ server")
        print("  2. copy npc_animations.json ไปที่ plugins/NPCPlugin/ ของ server")
        print("  3. ในเกมสั่ง /npc reload (หรือ restart server)")
        print("  4. /npc create <ชื่อโมเดลใหม่>")
        print("  * ไม่ต้อง rebuild wheel — ปลั๊กอินอ่าน npc_animations.json จาก data folder")
    else:
        print("build wheel ไม่สำเร็จ — รันเองด้วย: pip wheel . --no-deps -w dist")
else:
    print("(ข้ามขั้นตอนอัตโนมัติ: ไม่พบ src/endstone_npc/addon_types.json)")
