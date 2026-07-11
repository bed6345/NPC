# Endstone NPC Plugin (Citizens-like)

ปลั๊กอิน NPC สำหรับ **Endstone 0.11** (Minecraft Bedrock Dedicated Server)
เลียนแบบการทำงานของปลั๊กอิน Citizens ใน Java Edition

## ความสามารถ

- Spawn NPC หรือ mob ชนิดใดก็ได้ ให้ยืนอยู่กับที่ (ไม่เดินหนี, ไม่ despawn, โดนผลัก/ตกก็ถูกดึงกลับ)
- ผูก command กับ NPC — ผู้เล่นคลิก NPC แล้ว command รันทันที
- เลือกได้ว่า command รันในนาม **server console** หรือ **ผู้เล่นที่คลิก**
- ตั้งชื่อ NPC แสดงเหนือหัว (มองเห็นตลอด)
- ข้อมูลบันทึกลงไฟล์ JSON — NPC กลับมาครบหลัง server restart

## โครงสร้างโปรเจกต์

```
endstone-npc-plugin/
├── pyproject.toml              # metadata + entry point "endstone" (แทน plugin.toml)
├── README.md
└── src/endstone_npc/
    ├── __init__.py
    ├── plugin.py               # Plugin class: commands + event + scheduler
    ├── npc_manager.py          # โหลด/บันทึก JSON, spawn/ลบ/ตรึงตำแหน่ง NPC
    └── config.toml             # config default (ถูก copy ไป data folder ครั้งแรก)
```

> **หมายเหตุ:** ปลั๊กอิน Python ของ Endstone **ไม่ใช้ `plugin.toml`** (ไฟล์นั้นใช้กับ
> C++ plugin เท่านั้น) — metadata ทั้งหมดประกาศผ่าน class attribute (`api_version`,
> `commands`, `permissions`) และ entry point ใน `pyproject.toml` ตามมาตรฐาน Endstone

## วิธีติดตั้ง

ต้องมี Endstone >= 0.11 ติดตั้งอยู่แล้ว (`pip install endstone`)

### วิธีที่ 1: build เป็น wheel แล้ววางในโฟลเดอร์ plugins (แนะนำ)

```bash
cd endstone-npc-plugin
pip install build
python -m build --wheel
```

จะได้ไฟล์ `dist/endstone_npc_plugin-1.0.0-py3-none-any.whl`
นำไปวางในโฟลเดอร์ `plugins/` ของ server แล้ว restart server

### วิธีที่ 2: pip install ลง environment เดียวกับ endstone

```bash
cd endstone-npc-plugin
pip install .
```

แล้ว restart server — Endstone จะเจอปลั๊กอินผ่าน entry point อัตโนมัติ

เมื่อโหลดสำเร็จจะเห็นใน console:

```
[NPCPlugin] NPCPlugin เปิดใช้งานแล้ว (NPC ที่บันทึกไว้: 0 ตัว)
```

## คำสั่ง (ต้องเป็น OP)

| คำสั่ง | ความหมาย |
|---|---|
| `/npc create <type> [name]` | สร้าง NPC ที่ตำแหน่งผู้เล่น เช่น `/npc create npc ร้านค้า` — ช่อง type มี autocomplete รายชื่อ mob ให้เลือก |
| `/npc types [คำค้น]` | แสดงรายชื่อ entity type ที่ใช้ได้ เช่น `/npc types zombie` |
| `/npc createid <type> [name]` | สร้าง NPC จาก entity ของ addon โดยพิมพ์ชื่อเต็ม เช่น `/npc createid myaddon:robot บอท` |
| `/npc remove <id>` | ลบ NPC ตาม id |
| `/npc list` | แสดง NPC ทั้งหมด (● เขียว = ตัวอยู่ในโลก, แดง = chunk ยังไม่โหลด) |
| `/npc command add <id> <cmd>` | ผูก command กับ NPC (ผูกได้หลายอัน) |
| `/npc command remove <id> [index]` | ลบ command — ไม่ใส่ index ลบทั้งหมด, ใส่ index (เริ่มที่ 1) ลบเฉพาะอัน |
| `/npc setname <id> <name>` | เปลี่ยนชื่อเหนือหัว |

### เลือกผู้รัน command: prefix `console:` / `player:`

```
/npc command add 1 console:give {player} diamond 1   ← รันในนาม server console
/npc command add 1 player:spawn                      ← รันในนามผู้เล่นที่คลิก (ใช้สิทธิ์ผู้เล่น)
/npc command add 1 say สวัสดี {player}!               ← ไม่ใส่ prefix = ใช้ค่า default_run_as ใน config
```

placeholder `{player}` จะถูกแทนด้วยชื่อผู้เล่นที่คลิก NPC

### Custom NPC จาก addon ของปลั๊กอิน (แนะนำที่สุด)

ในโฟลเดอร์ `addon/` มี behavior + resource pack ที่ให้ entity `npcp:npc`
(spawn ด้วย `/npc create cnpc <ชื่อ>`) ซึ่งดีกว่า mob ธรรมดาเพราะถูกล็อกตั้งแต่ระดับ entity:

- `damage_sensor` ปิดดาเมจทุกชนิด → อมตะแท้ ไม่ต้องพึ่งปลั๊กอิน cancel event
- `movement = 0` + `knockback_resistance` + `pushable false` → ยืนนิ่งสนิท ผลักไม่ได้
- `persistent` → ไม่ despawn
- `behavior.look_at_player` → หันหน้ามองผู้เล่นที่เดินเข้าใกล้ (มีชีวิตชีวาแบบ Citizens)
- หน้าตาเป็นชาวบ้าน (โมเดล+texture ของ pack เอง ไม่พึ่ง vanilla)

นอกจาก `cnpc` ยังมี**โมเดล NPC สวย ๆ อีก 15 ตัว** (แปลงมาจาก Blockbench/Model Engine
ของ Java Edition) — spawn ด้วยชื่อสั้นได้เลย มี autocomplete:

`adventurer`, `king`, `miner`, `pirate`, `tavern` (มีแอนิเมชัน idle ขยับตลอด),
`dworf`, `farmermaxvers`, `kingdom_guardian`, `mageshaman`, `npcgreeting`
และของตกแต่ง `anchor`, `lootbag`, `minecart`, `tap`, `throne`

```
/npc create king พระราชา
/npc create pirate กัปตัน
```

**วิธีติดตั้ง pack บน server (BDS/Endstone):**

1. copy `addon/NPCPack_BP` ไปที่ `development_behavior_packs/` และ
   `addon/NPCPack_RP` ไปที่ `development_resource_packs/` ของ server
2. เพิ่มในไฟล์ `worlds/<ชื่อโลก>/world_behavior_packs.json`:
   ```json
   [{"pack_id": "3027883a-3b9b-4f42-8419-f378cd4b8007", "version": [1, 2, 1]}]
   ```
   และ `worlds/<ชื่อโลก>/world_resource_packs.json`:
   ```json
   [{"pack_id": "f3ac6d21-db6e-41dc-ae09-46210f330b12", "version": [1, 2, 1]}]
   ```
3. เปิดให้ client โหลด pack จาก server: ใน `server.properties` ตั้ง
   `texturepack-required=true` (ไม่ตั้งก็ได้ แต่ผู้เล่นต้อง import
   `npc_pack.mcaddon` เองในเครื่อง ไม่งั้นตัว NPC จะล่องหนเห็นแต่ชื่อ)
4. restart server แล้วสั่ง `/npc create cnpc ร้านค้า`

(ฝั่งผู้เล่น: ดับเบิลคลิก `addon/npc_pack.mcaddon` เพื่อ import เข้าเกม
หรือเปิด texturepack-required ใน server.properties ให้ client โหลดจาก server เอง)

### ชนิด entity ที่แนะนำ

- `npc` (`minecraft:npc`) — **แนะนำที่สุด**: ไม่เดิน ไม่มี gravity ผลักไม่ได้ หน้าตาเป็น NPC โดยเฉพาะ
- mob อื่น เช่น `villager_v2`, `pig`, `zombie` ก็ใช้ได้ — ปลั๊กอินจะใส่ slowness 255
  และดึงกลับตำแหน่งเดิมทุกวินาทีให้เอง
- ชื่อที่คุ้นจาก Java Edition ปลั๊กอินแปลงให้อัตโนมัติ เช่น `villager` → `villager_v2`,
  `zombified_piglin` → `zombie_pigman`, `evoker` → `evocation_illager`
- พิมพ์ชื่อผิด → ปลั๊กอินจะเดาชื่อใกล้เคียงให้ และไม่ทิ้ง record ค้าง
- entity จาก addon ใช้ได้ผ่าน `/npc createid` โดยพิมพ์ชื่อเต็มพร้อม namespace เช่น
  `/npc createid myaddon:robot`

## ตัวอย่างการใช้งาน

```
/npc create npc ร้านขายของ
→ สร้าง NPC สำเร็จ! id: 1

/npc command add 1 console:give {player} bread 5
/npc command add 1 console:tell {player} รับขนมปังไปกินนะ!
```

จากนั้นผู้เล่นคนไหนคลิก NPC ก็จะได้ขนมปัง 5 ก้อนพร้อมข้อความ

## Config (`plugins/NPCPlugin/config.toml` — สร้างอัตโนมัติครั้งแรก)

```toml
default_run_as = "console"   # ผู้รัน default เมื่อไม่ใส่ prefix: console | player
freeze_interval_ticks = 20   # ความถี่เช็คตำแหน่ง/respawn (20 = 1 วินาที)
interact_cooldown = 0.5      # วินาทีขั้นต่ำระหว่างคลิกของผู้เล่นคนเดิม (กัน event ยิงซ้ำ)
debug = false                # log การคลิก/ตี NPC ไว้ไล่ปัญหา (เปิดเฉพาะตอนจำเป็น)
```

ข้อมูล NPC เก็บที่ `plugins/NPCPlugin/npcs.json` — แก้มือได้ตอน server ปิด

## หลักการทำงาน (สำหรับคนอยากแก้โค้ด)

- **ระบุตัว NPC:** entity ทุกตัวถูกติด scoreboard tag `npcp:<id>` เพราะ runtime id
  ของ entity เปลี่ยนทุกครั้งที่ restart — tag + `npcs.json` คือ source of truth
- **ยืนอยู่กับที่:** ใส่ effect slowness 255 ซ้ำทุกรอบ (ผ่าน tag รวม `npcp_all`) +
  scheduler task ทุก `freeze_interval_ticks` เช็คว่า NPC ขยับเกิน 0.2 บล็อกหรือไม่
  ถ้าใช่ teleport กลับ
- **อมตะ:** cancel `ActorDamageEvent` และ `ActorKnockbackEvent` ของ NPC ทุกตัว —
  ตีไม่ตาย ไม่กระเด็น (ต่อให้ตายด้วย /kill ก็เกิดใหม่เองใน 1 วินาที)
- **ไม่ despawn:** task เดียวกันเช็คว่า entity ยังอยู่ไหม ถ้าหาย (despawn/ตาย/หลัง restart)
  จะ spawn ใหม่จากข้อมูลใน JSON ทันทีที่ chunk นั้นโหลด
- **การคลิก:** ใช้ `PlayerInteractActorEvent` — เจอ tag ของปลั๊กอินก็ cancel event
  (กันหน้าต่าง trade/UI เปิด) แล้วรัน command ที่ผูกไว้

## Checklist ทดสอบ

1. `/npc create npc ทดสอบ` → NPC โผล่ที่ตำแหน่งเรา มีชื่อเหนือหัว
2. ตี NPC → ไม่เสียเลือด ไม่กระเด็น ไม่ตาย และไม่เดินหนีออกจากจุดเดิม
3. `/npc command add 1 console:say {player} คลิกฉัน!` แล้วคลิก NPC → ข้อความขึ้น
4. `/npc command add 1 player:me กำลังคุยกับ NPC` แล้วคลิก → รันในนามผู้เล่น
5. `/npc list` → เห็น NPC พร้อมจำนวน command
6. `/npc setname 1 ชื่อใหม่` → ชื่อเหนือหัวเปลี่ยนทันที
7. restart server → NPC กลับมาที่เดิมพร้อม command ครบ
8. `/npc remove 1` → NPC หายและไม่กลับมาอีก

