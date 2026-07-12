"""จัดการข้อมูล NPC: โหลด/บันทึก JSON, spawn/ลบ entity, ตรึงตำแหน่ง (freeze)

หลักการระบุตัว NPC: runtime id ของ entity เปลี่ยนทุกครั้งที่ server restart
จึงติด scoreboard tag รูปแบบ "npcp:<id>" ไว้กับ entity แล้วใช้ id ของปลั๊กอิน
(เลข auto-increment ที่บันทึกลง npcs.json) เป็นตัวอ้างอิงถาวรแทน
"""

from __future__ import annotations

import json
import math
import os
from typing import TYPE_CHECKING, Optional

from endstone.actor import Actor
from endstone.command import CommandSenderWrapper
from endstone.level import Location

if TYPE_CHECKING:
    from .plugin import NPCPlugin

# prefix ของ scoreboard tag ที่ใช้ mark ว่า entity ตัวนี้เป็น NPC ของปลั๊กอิน
TAG_PREFIX = "npcp:"

# tag รวมที่ NPC ทุกตัวมี — ใช้ยิง /effect ครั้งเดียวถึงทุกตัว
COMMON_TAG = "npcp_all"

# ระยะ (ยกกำลังสอง) ที่ยอมให้ NPC ขยับก่อนถูกดึงกลับ — 0.04 = 0.2 บล็อก
MAX_DRIFT_SQ = 0.04


class NPCManager:
    """เก็บ record ของ NPC ทั้งหมดและ sync กับ entity จริงในโลก"""

    def __init__(self, plugin: "NPCPlugin") -> None:
        self.plugin = plugin
        self.data_file = os.path.join(plugin.data_folder, "npcs.json")
        self.next_id: int = 1
        # key เป็น str(id) เพื่อให้ตรงกับ JSON, value คือ record ของ NPC
        self.npcs: dict[str, dict] = {}
        # True เมื่อโหลดไฟล์สำเร็จ — เงื่อนไขก่อนกวาด entity กำพร้า
        self.load_ok = False
        # ตัวนับรอบของ freeze_tick ใช้เว้นจังหวะงานที่ไม่ต้องทำทุกวินาที
        self._pass = 0
        # นับถอยหลังยิง slowness ถี่พิเศษหลังมีตัว spawn ใหม่
        self._effect_boost = 0
        # console sender แบบเงียบ: กลืนข้อความ feedback (เช่น "Gave Slowness...")
        # ไม่ให้สแปม log แต่ error จริงยังส่งเข้า logger
        self._silent_sender: CommandSenderWrapper | None = None

    @property
    def silent_sender(self) -> CommandSenderWrapper:
        if self._silent_sender is None:
            self._silent_sender = CommandSenderWrapper(
                self.plugin.server.command_sender,
                on_message=lambda _: None,
                on_error=lambda msg: self.plugin.logger.warning(f"NPC command error: {msg}"),
            )
        return self._silent_sender

    # ------------------------------------------------------------------
    # Persistence (JSON)
    # ------------------------------------------------------------------

    def load(self) -> None:
        # load_ok = False จะปิดระบบเก็บกวาด entity กำพร้า (กันลบผิดตอนไฟล์พัง)
        self.load_ok = False
        if not os.path.exists(self.data_file):
            self.load_ok = True  # ยังไม่เคยมีข้อมูล = ปกติ
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.next_id = int(data.get("next_id", 1))
            self.npcs = data.get("npcs", {})
            self.load_ok = True
        except (OSError, ValueError) as e:
            # อย่าทำงานต่อแบบ list ว่างเฉย ๆ — สำรองไฟล์พังไว้ก่อน กันถูก
            # save ทับจนข้อมูลหายถาวร
            self.plugin.logger.error(f"โหลด npcs.json ไม่สำเร็จ: {e}")
            try:
                backup = self.data_file + ".bak"
                os.replace(self.data_file, backup)
                self.plugin.logger.error(f"สำรองไฟล์ที่พังไว้ที่ {backup} — กู้คืนได้ด้วยมือ")
            except OSError:
                pass

    def save(self) -> None:
        try:
            os.makedirs(self.plugin.data_folder, exist_ok=True)
            # เขียนลงไฟล์ชั่วคราวก่อนแล้วค่อยสลับ (atomic) — server ดับกลางคัน
            # ไฟล์หลักจะไม่พัง
            tmp = self.data_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"next_id": self.next_id, "npcs": self.npcs},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            os.replace(tmp, self.data_file)
        except OSError as e:
            self.plugin.logger.error(f"บันทึก npcs.json ไม่สำเร็จ: {e}")

    # ------------------------------------------------------------------
    # การค้นหา / ระบุตัว NPC
    # ------------------------------------------------------------------

    @staticmethod
    def tag_of(npc_id: int) -> str:
        return f"{TAG_PREFIX}{npc_id}"

    @staticmethod
    def get_npc_id_from_actor(actor: Actor) -> Optional[int]:
        """คืน id ของ NPC ถ้า actor ตัวนี้มี tag ของปลั๊กอิน, ไม่ใช่ก็คืน None"""
        for tag in actor.scoreboard_tags:
            if tag.startswith(TAG_PREFIX):
                try:
                    return int(tag[len(TAG_PREFIX):])
                except ValueError:
                    continue
        return None

    def find_actor(self, npc_id: int) -> Optional[Actor]:
        """หา entity จริงในโลกที่ผูกกับ NPC id นี้"""
        tag = self.tag_of(npc_id)
        for actor in self.plugin.server.level.actors:
            if actor.is_valid and tag in actor.scoreboard_tags:
                return actor
        return None

    # ------------------------------------------------------------------
    # สร้าง / spawn / ลบ
    # ------------------------------------------------------------------

    def create(
        self,
        actor_type: str,
        name: str,
        dimension_name: str,
        x: float,
        y: float,
        z: float,
        pitch: float,
        yaw: float,
    ) -> int:
        """สร้าง record ใหม่ + spawn entity, คืน id ที่ได้"""
        npc_id = self.next_id
        self.next_id += 1
        self.npcs[str(npc_id)] = {
            "type": actor_type,
            "name": name,
            "dimension": dimension_name,
            "x": x,
            "y": y,
            "z": z,
            "pitch": pitch,
            "yaw": yaw,
            "commands": [],  # list ของ {"cmd": str, "run_as": "console"|"player"}
        }
        self.save()
        self.spawn(npc_id)
        return npc_id

    def spawn(
        self,
        npc_id: int,
        dedupe: bool = True,
        chunk_cache: Optional[dict] = None,
    ) -> Optional[Actor]:
        """Spawn entity ของ NPC ตาม record

        - dedupe=True: สแกนลบตัวเก่าที่ tag ซ้ำก่อน (ใช้ตอน /npc create)
          freeze_tick ส่ง False เพราะเพิ่งสแกนทั้งโลกไปแล้ว ไม่ต้องสแกนซ้ำ
        - chunk_cache: dict ที่ freeze_tick ใช้แชร์รายการ chunk ที่โหลดแล้ว
          ข้ามหลาย NPC ในรอบเดียว (กันสแกน loaded_chunks ซ้ำต่อตัว)
        คืน None ถ้า dimension ไม่พบหรือ chunk ยังไม่โหลด — freeze_tick
        จะเรียกซ้ำเองเมื่อมีผู้เล่นเข้าใกล้จน chunk โหลด
        """
        record = self.npcs.get(str(npc_id))
        if record is None:
            return None

        tag = self.tag_of(npc_id)

        if dedupe:
            # ลบ entity เก่าที่ยังค้างอยู่ กันตัวซ้อน
            self.remove_all_actors(npc_id)

        dimension = self.plugin.server.level.get_dimension(record["dimension"])
        if dimension is None:
            return None

        # spawn ได้เฉพาะเมื่อ chunk นั้นโหลดอยู่ (มีผู้เล่นอยู่ใกล้)
        # endstone 0.11 ไม่มี is_chunk_loaded() — เช็คจากรายการ loaded_chunks แทน
        cx, cz = math.floor(record["x"] / 16), math.floor(record["z"] / 16)
        if chunk_cache is not None:
            loaded = chunk_cache.get(record["dimension"])
            if loaded is None:
                loaded = {(c.x, c.z) for c in dimension.loaded_chunks}
                chunk_cache[record["dimension"]] = loaded
            if (cx, cz) not in loaded:
                return None
        elif not any(c.x == cx and c.z == cz for c in dimension.loaded_chunks):
            return None

        try:
            location = Location(
                dimension,
                record["x"],
                record["y"],
                record["z"],
                record["pitch"],
                record["yaw"],
            )
            actor = dimension.spawn_actor(location, record["type"])
        except Exception as e:
            self.plugin.logger.error(
                f"spawn NPC #{npc_id} ({record['type']}) ไม่สำเร็จ: {e}"
            )
            return None
        if actor is None:
            return None

        actor.add_scoreboard_tag(tag)
        actor.add_scoreboard_tag(COMMON_TAG)
        actor.name_tag = record["name"]
        actor.is_name_tag_always_visible = True
        actor.set_rotation(record["yaw"], record["pitch"])
        return actor

    def remove_all_actors(self, npc_id: int) -> int:
        """ลบ entity ทุกตัวที่มี tag ของ id นี้ (เผื่อมีตัวซ้อนจาก restart)"""
        tag = self.tag_of(npc_id)
        count = 0
        for actor in list(self.plugin.server.level.actors):
            try:
                if actor.is_valid and tag in actor.scoreboard_tags:
                    actor.remove()
                    count += 1
            except Exception:
                pass
        return count

    def remove(self, npc_id: int) -> bool:
        """ลบ NPC ทั้ง entity (ทุกตัวที่ tag ตรง) และ record"""
        if str(npc_id) not in self.npcs:
            return False
        self.remove_all_actors(npc_id)
        del self.npcs[str(npc_id)]
        self.save()
        return True

    def set_name(self, npc_id: int, name: str) -> bool:
        record = self.npcs.get(str(npc_id))
        if record is None:
            return False
        record["name"] = name
        self.save()
        actor = self.find_actor(npc_id)
        if actor is not None:
            actor.name_tag = name
        return True

    # ------------------------------------------------------------------
    # Freeze loop — ทำงานเป็น scheduler task ซ้ำทุก N ticks
    # ------------------------------------------------------------------

    def freeze_tick(self) -> None:
        """ดึง NPC ที่ขยับกลับที่เดิม และ respawn ตัวที่หายไป

        สแกน level.actors รอบเดียวแล้วทำ map id -> actor เพื่อไม่ต้อง
        วนหา entity ซ้ำทีละตัว (ประหยัดเวลาเมื่อในโลกมี entity เยอะ)
        """
        self._pass += 1

        # ไม่มี NPC ในระบบ = ไม่มีอะไรต้องตรึง — เหลือแค่กวาดตัวกำพร้า
        # ซึ่งนาน ๆ ทำทีก็พอ (ทุก 10 รอบ ~10 วิ) ลดภาระตอนเซิร์ฟไม่ได้ใช้ NPC
        if not self.npcs and self._pass % 10 != 0:
            return

        found: dict[int, Actor] = {}
        for actor in self.plugin.server.level.actors:
            if not actor.is_valid:
                continue
            nid = self.get_npc_id_from_actor(actor)
            if nid is None:
                continue

            # entity กำพร้า (มี tag แต่ record ถูกลบไปแล้ว เช่นไฟล์เคยหาย
            # หรือ /npc remove รุ่นเก่าลบไม่หมด) -> กวาดทิ้ง
            # ทำเฉพาะเมื่อโหลดไฟล์สำเร็จ กันลบผิดตอน npcs.json พัง
            if str(nid) not in self.npcs:
                if self.load_ok:
                    try:
                        actor.remove()
                        self.plugin.logger.info(f"ลบ NPC กำพร้า (id {nid}) ที่ไม่มีใน npcs.json")
                    except Exception:
                        pass
                continue

            # ตัวซ้อน: id เดียวกันมีหลาย entity (race ตอน restart) -> เก็บตัวแรก ลบที่เหลือ
            if nid in found:
                try:
                    actor.remove()
                    self.plugin.logger.info(f"ลบ NPC ตัวซ้อนของ id {nid}")
                except Exception:
                    pass
                continue

            found[nid] = actor
            # เผื่อ NPC ที่สร้างจากเวอร์ชันเก่ายังไม่มี tag รวม
            actor.add_scoreboard_tag(COMMON_TAG)

        if not self.npcs:
            return

        # cache รายการ chunk ที่โหลดแล้ว แชร์กันทุก NPC ในรอบนี้
        chunk_cache: dict = {}
        spawned_any = False

        players = list(self.plugin.server.online_players)

        for key, record in self.npcs.items():
            npc_id = int(key)
            actor = found.get(npc_id)

            if actor is None or actor.is_dead:
                if self.spawn(npc_id, dedupe=False, chunk_cache=chunk_cache) is not None:
                    spawned_any = True
                continue

            dx = actor.location.x - record["x"]
            dy = actor.location.y - record["y"]
            dz = actor.location.z - record["z"]
            if dx * dx + dy * dy + dz * dz > MAX_DRIFT_SQ:
                dimension = self.plugin.server.level.get_dimension(record["dimension"])
                if dimension is None:
                    continue
                try:
                    actor.teleport(
                        Location(
                            dimension,
                            record["x"],
                            record["y"],
                            record["z"],
                            record["pitch"],
                            record["yaw"],
                        )
                    )
                except Exception:
                    pass

            look_range = record.get("look_at", 0)
            if look_range > 0 and players:
                look_range_sq = look_range * look_range
                nearest = None
                min_dsq = look_range_sq
                nx, ny, nz = record["x"], record["y"], record["z"]
                for p in players:
                    if p.dimension.name != record["dimension"]:
                        continue
                    pl = p.location
                    dsq = (pl.x - nx) ** 2 + (pl.y - ny) ** 2 + (pl.z - nz) ** 2
                    if dsq < min_dsq:
                        min_dsq = dsq
                        nearest = p
                if nearest is not None:
                    pl = nearest.location
                    ldx = pl.x - nx
                    ldz = pl.z - nz
                    ldy = pl.y - ny
                    dist_xz = math.sqrt(ldx * ldx + ldz * ldz)
                    if dist_xz > 0.01:
                        actor.set_rotation(
                            -math.degrees(math.atan2(ldx, ldz)),
                            -math.degrees(math.atan2(ldy, dist_xz)),
                        )
                else:
                    actor.set_rotation(record["yaw"], record["pitch"])

        # slowness กันเดิน: effect อยู่ได้ 60 วิ จึงยิงซ้ำแค่ทุก 40 รอบ (~40 วิ)
        # แต่ช่วง 3 รอบหลังมีตัว spawn ใหม่จะยิงทุกรอบ เพราะ selector
        # อาจยังมองไม่เห็น entity ที่เพิ่งเกิดใน tick เดียวกัน
        # ไวยากรณ์: effect <target> <effect> <วินาที> <ระดับ 0-255> <ซ่อน particle>
        if spawned_any:
            self._effect_boost = 3
        if (found or spawned_any) and (self._effect_boost > 0 or self._pass % 40 == 1):
            self._effect_boost = max(0, self._effect_boost - 1)
            self.plugin.server.dispatch_command(
                self.silent_sender,
                f"effect @e[tag={COMMON_TAG}] slowness 60 255 true",
            )
