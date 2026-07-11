"""รายชื่อ entity ของ Bedrock ที่ spawn ได้ + alias สำหรับชื่อที่คนมักพิมพ์ผิด

ใช้สร้าง enum ใน command usage เพื่อให้เกมขึ้น autocomplete ตอนพิมพ์
/npc create และใช้เดาชื่อใกล้เคียงเมื่อพิมพ์ผิด
(endstone 0.11 ยังไม่มี parameter type "entity_type" จึงต้องฝังรายชื่อเอง)
"""

from __future__ import annotations

import difflib
import json
import os

# entity จาก addon ของปลั๊กอิน (NPCPack) — อมตะ/ยืนนิ่งตั้งแต่ระดับ entity
# ต้องติดตั้ง addon/NPCPack_BP + NPCPack_RP ในโลกก่อนถึงจะ spawn ได้
# cnpc = ชาวบ้านโมเดลพื้นฐาน ที่เหลือโหลดจาก addon_types.json ซึ่ง
# tools/bbmodel2bedrock.py เขียนให้อัตโนมัติตอนแปลงโมเดลใหม่
_ADDON_TYPES_FILE = os.path.join(os.path.dirname(__file__), "addon_types.json")
try:
    with open(_ADDON_TYPES_FILE, encoding="utf-8") as _f:
        ADDON_TYPES = ["cnpc"] + sorted(json.load(_f))
except (OSError, ValueError):
    ADDON_TYPES = ["cnpc"]

# identifier จริงของ Bedrock (ไม่ใส่ prefix minecraft:)
VANILLA_TYPES = [
    "npc",
    "allay", "armadillo", "axolotl", "bat", "bee", "blaze", "bogged", "breeze",
    "camel", "cat", "cave_spider", "chicken", "cod", "cow", "creaking", "creeper",
    "dolphin", "donkey", "drowned", "elder_guardian", "ender_dragon", "enderman",
    "endermite", "evocation_illager", "fox", "frog", "ghast", "glow_squid", "goat",
    "guardian", "happy_ghast", "hoglin", "horse", "husk", "iron_golem", "llama",
    "magma_cube", "mooshroom", "mule", "ocelot", "panda", "parrot", "phantom",
    "pig", "piglin", "piglin_brute", "pillager", "polar_bear", "pufferfish",
    "rabbit", "ravager", "salmon", "sheep", "shulker", "silverfish", "skeleton",
    "skeleton_horse", "slime", "sniffer", "snow_golem", "spider", "squid", "stray",
    "strider", "tadpole", "trader_llama", "tropicalfish", "turtle", "vex",
    "villager_v2", "vindicator", "wandering_trader", "warden", "witch", "wither",
    "wither_skeleton", "wolf", "zoglin", "zombie", "zombie_horse", "zombie_pigman",
    "zombie_villager_v2",
]

# ชื่อที่คนคุ้นจาก Java Edition / ชื่อเก่า -> identifier จริงของ Bedrock
# (ค่าที่มี namespace เช่น npcp:npc จะถูกใช้ตรง ๆ ไม่เติม minecraft:)
ALIASES = {
    "cnpc": "npcp:npc",
    # โมเดลจาก addon: ชื่อสั้น -> npcp:<ชื่อ>
    **{t: f"npcp:{t}" for t in ADDON_TYPES if t != "cnpc"},
    "villager": "villager_v2",
    "zombie_villager": "zombie_villager_v2",
    "zombified_piglin": "zombie_pigman",
    "piglin_zombie": "zombie_pigman",
    "mushroom_cow": "mooshroom",
    "tropical_fish": "tropicalfish",
    "snowman": "snow_golem",
    "evoker": "evocation_illager",
}


# รายชื่อรวมสำหรับ autocomplete / /npc types / ตัวเดาชื่อ
ALL_TYPES = ADDON_TYPES + VANILLA_TYPES


def normalize(raw: str) -> str:
    """แปลงชื่อที่ผู้ใช้พิมพ์เป็น identifier เต็ม เช่น pig -> minecraft:pig

    ชื่อที่มี namespace อื่น (entity จาก addon เช่น myaddon:robot) ปล่อยผ่านตามเดิม
    """
    name = raw.strip().lower()
    if ":" in name:
        namespace, short = name.split(":", 1)
        if namespace != "minecraft":
            return name  # addon entity
        name = short
    name = ALIASES.get(name, name)
    if ":" in name:
        return name  # alias ชี้ไปที่ entity ของ addon (เช่น cnpc -> npcp:npc)
    return f"minecraft:{name}"


def suggest(raw: str, n: int = 3) -> list[str]:
    """คืนรายชื่อ type ที่สะกดใกล้เคียงกับที่ผู้ใช้พิมพ์"""
    name = raw.strip().lower().removeprefix("minecraft:")
    return difflib.get_close_matches(name, ALL_TYPES + list(ALIASES), n=n, cutoff=0.5)
