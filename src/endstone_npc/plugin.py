"""NPCPlugin — ปลั๊กอิน NPC สไตล์ Citizens สำหรับ Endstone 0.11

ความสามารถ:
- /npc create <type> [name]        สร้าง NPC ที่ตำแหน่งผู้เล่น (ยืนอยู่กับที่ ไม่ despawn)
- /npc remove <id>                 ลบ NPC
- /npc list                        แสดง NPC ทั้งหมด
- /npc command add <id> <cmd>      ผูก command (prefix "console:"/"player:" เลือกผู้รัน)
- /npc command remove <id> [index] ลบ command ที่ผูกไว้
- /npc setname <id> <name>         เปลี่ยนชื่อเหนือหัว
- คลิก NPC -> รัน command ที่ผูกไว้ (รองรับ placeholder {player})
- ข้อมูลบันทึกลง <data_folder>/npcs.json อยู่ครบหลัง server restart
"""

# หมายเหตุ: ห้ามใส่ `from __future__ import annotations` ในไฟล์นี้!
# มันทำให้ annotation ของ event handler กลายเป็น string แล้ว endstone
# จะ register handler ไม่ได้ (error: invalid event handler signature)
import time

from endstone import ColorFormat, Player
from endstone.command import Command, CommandSender
from endstone.event import (
    ActorDamageEvent,
    ActorKnockbackEvent,
    PlayerInteractActorEvent,
    event_handler,
)
from endstone.plugin import Plugin

from . import entity_types
from .npc_manager import NPCManager

# enum รายชื่อ mob + โมเดลจาก addon สำหรับ autocomplete ตอนพิมพ์ /npc create
_TYPE_ENUM = "|".join(entity_types.ALL_TYPES)


class NPCPlugin(Plugin):
    prefix = "NPCPlugin"
    api_version = "0.11"

    commands = {
        "npc": {
            "description": "จัดการ NPC (สไตล์ Citizens)",
            "usages": [
                # create: enum -> เกมขึ้นรายชื่อ type ให้เลือก
                # (ห้ามมี overload (create) ซ้ำสองอัน ไม่งั้น client ฟ้อง syntax error)
                f"/npc (create)<npc_create: NpcCreate> ({_TYPE_ENUM})<type: NpcTypes> [name: message]",
                # createid: พิมพ์ชื่อ entity อิสระ สำหรับ entity จาก addon เช่น myaddon:robot
                "/npc (createid)<npc_createid: NpcCreateId> <type: str> [name: message]",
                "/npc (types)<npc_types: NpcTypesList> [filter: str]",
                "/npc (remove)<npc_remove: NpcRemove> <id: int>",
                "/npc (list)<npc_list: NpcList>",
                "/npc (setname)<npc_setname: NpcSetname> <id: int> <name: message>",
                # add/remove ต้องเป็น enum เดียวกันใน usage เดียว —
                # แยกเป็นสอง overload ที่ขึ้นต้น (command) เหมือนกันจะทำให้
                # client ฟ้อง "Syntax error: Unexpected add"
                "/npc (command)<npc_cmd: NpcCmd> (add|remove)<cmd_action: NpcCmdAction> <id: int> [cmd: message]",
            ],
            "permissions": ["npc_plugin.command.npc"],
        }
    }

    permissions = {
        "npc_plugin.command.npc": {
            "description": "อนุญาตให้ใช้คำสั่ง /npc",
            "default": "op",  # เฉพาะ OP เท่านั้น
        }
    }

    def __init__(self) -> None:
        super().__init__()
        self.manager: NPCManager | None = None
        # ค่า config (ถูก override จาก config.toml ใน on_enable)
        self.default_run_as = "console"
        self.freeze_interval_ticks = 20
        self.interact_cooldown = 0.5
        self.debug = False  # log การคลิก/ตี NPC เพื่อช่วยไล่ปัญหา (เปิดใน config.toml)
        # กัน PlayerInteractActorEvent ยิงซ้ำ: ชื่อผู้เล่น -> เวลาคลิกล่าสุด
        self._last_interact: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enable(self) -> None:
        self._load_config()

        self.manager = NPCManager(self)
        self.manager.load()

        # ฟัง event การคลิก entity
        self.register_events(self)

        # งานวนซ้ำ: ตรึงตำแหน่ง NPC + respawn ตัวที่หาย + กวาดตัวซ้อน/ตัวกำพร้า
        # (delay 100 ticks = 5 วิ เผื่อให้โลก stream entity ที่ save ไว้เข้ามาก่อน
        # กัน race ที่ทำให้ spawn ตัวใหม่ซ้อนกับตัวเก่าตอน restart)
        self.server.scheduler.run_task(
            self,
            self.manager.freeze_tick,
            delay=100,
            period=self.freeze_interval_ticks,
        )

        self.logger.info(
            f"NPCPlugin v1.2.0 เปิดใช้งานแล้ว "
            f"(NPC ที่บันทึกไว้: {len(self.manager.npcs)} ตัว, debug={self.debug})"
        )

    def on_disable(self) -> None:
        if self.manager is not None:
            self.manager.save()

    def _load_config(self) -> None:
        """คัดลอก config.toml ตัวอย่างไปที่ data folder (ครั้งแรก) แล้วอ่านค่า"""
        try:
            self.save_default_config()
            cfg = self.config
            run_as = str(cfg.get("default_run_as", "console")).lower()
            self.default_run_as = run_as if run_as in ("console", "player") else "console"
            self.freeze_interval_ticks = max(1, int(cfg.get("freeze_interval_ticks", 20)))
            self.interact_cooldown = float(cfg.get("interact_cooldown", 0.5))
            self.debug = bool(cfg.get("debug", False))
        except Exception as e:
            self.logger.warning(f"อ่าน config.toml ไม่ได้ ใช้ค่า default แทน: {e}")

    # ------------------------------------------------------------------
    # Events: ปกป้อง NPC — ห้ามโดนดาเมจ (ตีไม่ตาย) และห้ามกระเด็น
    # ------------------------------------------------------------------

    @event_handler
    def on_actor_damage(self, event: ActorDamageEvent) -> None:
        npc_id = NPCManager.get_npc_id_from_actor(event.actor)
        if npc_id is None:
            return  # entity ธรรมดา — จบเร็วที่สุด ไม่ log (event นี้ยิงถี่มากทั้งเซิร์ฟ)
        if self.debug:
            try:
                by = event.damage_source.actor
                by_name = by.name if by is not None else "?"
            except Exception:
                by_name = "?"
            self.logger.info(
                f"[debug] damage: {event.actor.type} by {by_name} -> npc_id={npc_id}"
            )
        event.is_cancelled = True
        # การ "กด" NPC บน Bedrock ส่วนใหญ่นับเป็นโจมตี (คลิกซ้าย/แตะบนมือถือ)
        # จึงให้การตีก็ trigger command ด้วย เหมือน Citizens ใน Java
        attacker = event.damage_source.actor
        if isinstance(attacker, Player):
            self._run_npc_commands(attacker, npc_id)

    @event_handler
    def on_actor_knockback(self, event: ActorKnockbackEvent) -> None:
        if NPCManager.get_npc_id_from_actor(event.actor) is not None:
            event.is_cancelled = True

    # ------------------------------------------------------------------
    # Event: ผู้เล่นคลิก NPC -> รัน command ที่ผูกไว้
    # ------------------------------------------------------------------

    @event_handler
    def on_player_interact_actor(self, event: PlayerInteractActorEvent) -> None:
        npc_id = NPCManager.get_npc_id_from_actor(event.actor)
        if self.debug:
            self.logger.info(
                f"[debug] interact: {event.actor.type} by {event.player.name} -> npc_id={npc_id}"
            )
        if npc_id is None:
            return  # entity ธรรมดา ไม่ใช่ NPC ของเรา

        # กันพฤติกรรม interact ปกติ (เช่น เปิดหน้าต่าง trade / นั่งม้า)
        event.is_cancelled = True
        self._run_npc_commands(event.player, npc_id)

    def _run_npc_commands(self, player: Player, npc_id: int) -> None:
        """รัน command ทุกอันที่ผูกกับ NPC — เรียกได้ทั้งจากการคลิกขวาและการตี"""
        record = self.manager.npcs.get(str(npc_id))
        if record is None:
            return

        # Bedrock ยิง event ถี่มาก (และตี+คลิกอาจมาพร้อมกัน) — cooldown ต่อผู้เล่น
        now = time.monotonic()
        if now - self._last_interact.get(player.name, 0.0) < self.interact_cooldown:
            return
        self._last_interact[player.name] = now

        if not record["commands"]:
            player.send_message(
                f"{ColorFormat.YELLOW}NPC {record['name']} ยังไม่มี command ผูกไว้"
            )
            return

        for entry in record["commands"]:
            # {player} = ชื่อผู้เล่นที่คลิก
            cmd = entry["cmd"].replace("{player}", player.name).lstrip("/")
            if self.debug:
                self.logger.info(f"[debug] run ({entry.get('run_as')}): /{cmd}")
            try:
                if entry.get("run_as") == "player":
                    # รันในนามผู้เล่นที่คลิก (ใช้สิทธิ์ของผู้เล่นเอง)
                    player.perform_command(cmd)
                else:
                    # รันในนาม server console
                    self.server.dispatch_command(self.server.command_sender, cmd)
            except Exception as e:
                self.logger.error(f"NPC #{npc_id} run '{cmd}' failed: {e}")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        if command.name != "npc" or not args:
            return False

        action = args[0]
        try:
            if action in ("create", "createid"):
                return self._cmd_create(sender, args)
            if action == "remove":
                return self._cmd_remove(sender, args)
            if action == "list":
                return self._cmd_list(sender)
            if action == "types":
                return self._cmd_types(sender, args)
            if action == "setname":
                return self._cmd_setname(sender, args)
            if action == "command":
                if len(args) >= 2 and args[1] == "add":
                    return self._cmd_command_add(sender, args)
                if len(args) >= 2 and args[1] == "remove":
                    return self._cmd_command_remove(sender, args)
        except Exception as e:
            sender.send_error_message(f"เกิดข้อผิดพลาด: {e}")
            self.logger.error(f"/npc error: {e}")
            return True
        return False

    def _get_record(self, sender: CommandSender, npc_id: int):
        record = self.manager.npcs.get(str(npc_id))
        if record is None:
            sender.send_error_message(f"ไม่พบ NPC id {npc_id} (ดูรายการด้วย /npc list)")
        return record

    def _cmd_create(self, sender: CommandSender, args: list[str]) -> bool:
        # ต้องเป็นผู้เล่นเพราะใช้ตำแหน่ง/ทิศทางของผู้สั่งเป็นจุดเกิด
        if not isinstance(sender, Player):
            sender.send_error_message("คำสั่งนี้ใช้ได้เฉพาะผู้เล่นในเกม")
            return True

        # แปลงชื่อเป็น identifier จริง (แก้ alias เช่น villager -> villager_v2)
        actor_type = entity_types.normalize(args[1])

        loc = sender.location
        dimension_name = sender.dimension.name
        # ไม่ใส่ชื่อ -> ตั้งชื่อ default ตาม id ที่กำลังจะได้
        if len(args) > 2 and args[2].strip():
            name = args[2].strip()
        else:
            name = f"NPC #{self.manager.next_id}"

        npc_id = self.manager.create(
            actor_type=actor_type,
            name=name,
            dimension_name=dimension_name,
            x=loc.x,
            y=loc.y,
            z=loc.z,
            pitch=loc.pitch,
            yaw=loc.yaw,
        )
        actor = self.manager.find_actor(npc_id)
        if actor is None:
            # spawn ไม่สำเร็จ (ส่วนใหญ่คือชื่อ type ผิด) -> ถอน record ทิ้งอัตโนมัติ
            self.manager.remove(npc_id)
            msg = f"spawn ไม่สำเร็จ — ไม่รู้จัก entity type '{args[1]}'"
            close = entity_types.suggest(args[1])
            if close:
                msg += f" ({ColorFormat.YELLOW}ใกล้เคียง: {', '.join(close)}{ColorFormat.RED})"
            sender.send_error_message(msg)
            sender.send_message(
                f"{ColorFormat.GRAY}ดูรายชื่อ type ทั้งหมด: /npc types [คำค้น]"
            )
            return True
        sender.send_message(
            f"{ColorFormat.GREEN}สร้าง NPC สำเร็จ! id: {ColorFormat.YELLOW}{npc_id}"
            f"{ColorFormat.GREEN} ชื่อ: {self.manager.npcs[str(npc_id)]['name']} "
            f"({actor_type})"
        )
        sender.send_message(
            f"{ColorFormat.GRAY}ผูก command ด้วย /npc command add {npc_id} <คำสั่ง>"
        )
        return True

    def _cmd_types(self, sender: CommandSender, args: list[str]) -> bool:
        """แสดงรายชื่อ entity type ที่ใช้ได้ (กรองด้วยคำค้นได้)"""
        keyword = args[1].lower() if len(args) > 1 and args[1] else ""
        matched = [t for t in entity_types.ALL_TYPES if keyword in t]
        if not matched:
            sender.send_error_message(f"ไม่พบ type ที่มีคำว่า '{keyword}'")
            return True
        sender.send_message(
            f"{ColorFormat.GOLD}=== entity type ที่ใช้ได้ ({len(matched)}) ==="
        )
        sender.send_message(f"{ColorFormat.WHITE}{', '.join(sorted(matched))}")
        sender.send_message(
            f"{ColorFormat.GRAY}entity จาก addon ก็ใช้ได้ โดยพิมพ์ชื่อเต็ม เช่น myaddon:robot"
        )
        return True

    def _cmd_remove(self, sender: CommandSender, args: list[str]) -> bool:
        npc_id = int(args[1])
        record = self._get_record(sender, npc_id)
        if record is None:
            return True
        name = record["name"]
        self.manager.remove(npc_id)
        sender.send_message(f"{ColorFormat.GREEN}ลบ NPC {name} (id {npc_id}) แล้ว")
        return True

    def _cmd_list(self, sender: CommandSender) -> bool:
        if not self.manager.npcs:
            sender.send_message(f"{ColorFormat.YELLOW}ยังไม่มี NPC — สร้างด้วย /npc create <type> <name>")
            return True
        sender.send_message(f"{ColorFormat.GOLD}=== NPC ทั้งหมด ({len(self.manager.npcs)} ตัว) ===")
        for key, record in sorted(self.manager.npcs.items(), key=lambda kv: int(kv[0])):
            alive = self.manager.find_actor(int(key)) is not None
            status = f"{ColorFormat.GREEN}●" if alive else f"{ColorFormat.RED}●"
            sender.send_message(
                f"{status} {ColorFormat.YELLOW}#{key} {ColorFormat.WHITE}{record['name']} "
                f"{ColorFormat.GRAY}({record['type']}) "
                f"@ {record['x']:.1f}, {record['y']:.1f}, {record['z']:.1f} "
                f"[{record['dimension']}] — {len(record['commands'])} command"
            )
        return True

    def _cmd_setname(self, sender: CommandSender, args: list[str]) -> bool:
        npc_id = int(args[1])
        name = args[2]
        if self._get_record(sender, npc_id) is None:
            return True
        self.manager.set_name(npc_id, name)
        sender.send_message(f"{ColorFormat.GREEN}เปลี่ยนชื่อ NPC #{npc_id} เป็น '{name}' แล้ว")
        return True

    def _cmd_command_add(self, sender: CommandSender, args: list[str]) -> bool:
        npc_id = int(args[2])
        record = self._get_record(sender, npc_id)
        if record is None:
            return True

        if len(args) < 4 or not args[3].strip():
            sender.send_error_message(
                f"ระบุ command ด้วย เช่น /npc command add {npc_id} console:say สวัสดี {{player}}"
            )
            return True
        raw = args[3].strip()
        # เลือกผู้รันด้วย prefix: "console:..." หรือ "player:..."
        # ไม่ใส่ prefix -> ใช้ default_run_as จาก config.toml
        run_as = self.default_run_as
        if raw.lower().startswith("console:"):
            run_as, raw = "console", raw[len("console:"):].strip()
        elif raw.lower().startswith("player:"):
            run_as, raw = "player", raw[len("player:"):].strip()
        if not raw:
            sender.send_error_message("command ว่างเปล่า")
            return True

        record["commands"].append({"cmd": raw, "run_as": run_as})
        self.manager.save()
        sender.send_message(
            f"{ColorFormat.GREEN}ผูก command กับ NPC #{npc_id} แล้ว "
            f"(รันในนาม: {run_as}) — ตอนนี้มี {len(record['commands'])} command"
        )
        return True

    def _cmd_command_remove(self, sender: CommandSender, args: list[str]) -> bool:
        npc_id = int(args[2])
        record = self._get_record(sender, npc_id)
        if record is None:
            return True

        if len(args) > 3 and args[3].strip():
            # ลบเฉพาะลำดับที่ระบุ (index เริ่มที่ 1 ตามที่แสดงให้ผู้ใช้เห็น)
            index = int(args[3].strip())
            if not 1 <= index <= len(record["commands"]):
                sender.send_error_message(
                    f"index ต้องอยู่ระหว่าง 1-{len(record['commands'])}"
                )
                return True
            removed = record["commands"].pop(index - 1)
            self.manager.save()
            sender.send_message(
                f"{ColorFormat.GREEN}ลบ command '{removed['cmd']}' ออกจาก NPC #{npc_id} แล้ว"
            )
        else:
            count = len(record["commands"])
            record["commands"] = []
            self.manager.save()
            sender.send_message(
                f"{ColorFormat.GREEN}ลบ command ทั้งหมด ({count} รายการ) ออกจาก NPC #{npc_id} แล้ว"
            )
        return True
