# Endstone NPC Plugin (Citizens-like)

ปลั๊กอิน NPC สำหรับ **Endstone 0.11** (Minecraft Bedrock Dedicated Server)
เลียนแบบการทำงานของปลั๊กอิน Citizens ใน Java Edition

## ความสามารถ

- Spawn NPC หรือ mob ชนิดใดก็ได้ ให้ยืนอยู่กับที่ (ไม่เดินหนี, ไม่ despawn, โดนผลัก/ตกก็ถูกดึงกลับ)
- ผูก command กับ NPC — ผู้เล่นคลิก NPC แล้ว command รันทันที
- เลือกได้ว่า command รันในนาม **server console** หรือ **ผู้เล่นที่คลิก**
- ตั้งชื่อ NPC แสดงเหนือหัว (มองเห็นตลอด)
- **NPC หันหน้ามองผู้เล่น** — ตั้งค่าแยกเฉพาะตัวด้วย `/npc look` กำหนดระยะได้
- **ตั้ง animation** ให้ NPC เล่นเมื่อถูกคลิก (เฉพาะ NPC จาก addon ที่มี animation)
- ข้อมูลบันทึกลงไฟล์ JSON — NPC กลับมาครบหลัง server restart

## โครงสร้างโปรเจกต์

```
endstone-npc-plugin/
├── pyproject.toml              # metadata + entry point "endstone" (แทน plugin.toml)
├── README.md
├── src/endstone_npc/
│   ├── __init__.py
│   ├── plugin.py               # Plugin class: commands + event + scheduler
│   ├── npc_manager.py          # โหลด/บันทึก JSON, spawn/ลบ/ตรึงตำแหน่ง NPC
│   ├── entity_types.py         # รายชื่อ entity + alias + ข้อมูล animation
│   └── config.toml             # config default (ถูก copy ไป data folder ครั้งแรก)
├── addon/                      # Behavior + Resource Pack (โมเดล NPC สวย ๆ 30 ตัว)
├── java_npc/                   # ไฟล์ต้นฉบับ Blockbench blueprints + textures
├── tools/                      # Scripts แปลง Blockbench model เป็น Bedrock addon
│   └── bbmodel2bedrock.py      # แปลง .bbmodel → addon + สร้าง npc_animations.json
└── npc_animations.json         # (auto-gen) รายชื่อ animation ของแต่ละ NPC type
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

จะได้ไฟล์ `dist/endstone_npc_plugin-1.1.4-py3-none-any.whl`
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
| `/npc look <id> [range]` | เปิด/ปิดการมองหน้าผู้เล่น — ไม่ใส่ range = toggle on/off, ใส่ range = กำหนดระยะ (0 = ปิด) |
| `/npc animations set <id> [animation]` | ตั้ง animation เล่นเมื่อคลิก — ไม่ใส่ชื่อ animation จะแสดงรายการที่มีให้เลือก |
| `/npc animations remove <id>` | ลบ animation ที่ตั้งไว้ |
| `/npc reload` | โหลด config และข้อมูล animation ใหม่โดยไม่ต้อง restart server |

### เลือกผู้รัน command: prefix `console:` / `player:`

```
/npc command add 1 console:give {player} diamond 1   ← รันในนาม server console
/npc command add 1 player:spawn                      ← รันในนามผู้เล่นที่คลิก (ใช้สิทธิ์ผู้เล่น)
/npc command add 1 say สวัสดี {player}!               ← ไม่ใส่ prefix = ใช้ค่า default_run_as ใน config
```

placeholder `{player}` จะถูกแทนด้วยชื่อผู้เล่นที่คลิก NPC

### ตั้ง NPC ให้มองหน้าผู้เล่น

```
/npc look 1
→ เปิด: NPC #1 จะหันหน้ามองผู้เล่นในระยะ 3 บล็อก (ค่า default จาก config)

/npc look 1 5
→ NPC #1 จะมองผู้เล่นในระยะ 5 บล็อก

/npc look 1
→ ปิด: NPC #1 หยุดหันหน้าตามผู้เล่น (toggle)

/npc look 1 0
→ ปิดเช่นกัน (range = 0)
```

### ตั้ง Animation เมื่อคลิก NPC

NPC จาก addon ที่มี animation สามารถตั้งให้เล่น animation เมื่อผู้เล่นคลิกได้:

```
/npc create king พระราชา
→ สร้าง NPC สำเร็จ! id: 1

/npc animations set 1
→ แสดงรายการ animation ที่มี: idle, alone, fidget, greet

/npc animations set 1 greet
→ ตั้ง animation 'greet' แล้ว — คลิก NPC จะเล่น animation โค้งคำนับ

/npc animations remove 1
→ ลบ animation ที่ตั้งไว้
```

ถ้าพิมพ์ชื่อ animation ผิด ปลั๊กอินจะบอกว่ามีอันไหนเลือกได้บ้าง
animation ทำงานร่วมกับ command ได้ — คลิกครั้งเดียวทั้งเล่น animation และรัน command

### เพิ่มโมเดล NPC ใหม่โดยไม่ต้อง build ปลั๊กอินใหม่

เมื่อแปลงโมเดล Blockbench ใหม่ด้วย `tools/bbmodel2bedrock.py` ตัว script จะสร้างไฟล์
`npc_animations.json` ให้อัตโนมัติ (รายชื่อ animation ของแต่ละ NPC type) วิธีอัปเดต:

1. รัน `tools/bbmodel2bedrock.py` ตามปกติ — ได้ addon files + `npc_animations.json` ที่ root โปรเจกต์
2. copy `npc_animations.json` ไปวางที่ `plugins/NPCPlugin/npc_animations.json` บน server
3. ในเกมสั่ง `/npc reload` — ปลั๊กอินจะอ่าน config + animation data ใหม่ทันที

**ไม่ต้อง build wheel ใหม่** เมื่อเพิ่มโมเดล — แค่ copy ไฟล์ JSON แล้ว reload

ตัวอย่าง `npc_animations.json`:
```json
{
  "adventurer": ["idle", "alone", "fidget", "greet"],
  "king": ["idle", "alone", "fidget", "greet"],
  "pirate": ["idle", "alone", "fidget", "greet"]
}
```

### Custom NPC จาก addon ของปลั๊กอิน (แนะนำที่สุด)

ในโฟลเดอร์ `addon/` มี behavior + resource pack ที่ให้ entity `npcp:npc`
(spawn ด้วย `/npc create cnpc <ชื่อ>`) ซึ่งดีกว่า mob ธรรมดาเพราะถูกล็อกตั้งแต่ระดับ entity:

- `damage_sensor` ปิดดาเมจทุกชนิด → อมตะแท้ ไม่ต้องพึ่งปลั๊กอิน cancel event
- `movement = 0` + `knockback_resistance` + `pushable false` → ยืนนิ่งสนิท ผลักไม่ได้
- `persistent` → ไม่ despawn
- หน้าตาเป็นชาวบ้าน (โมเดล+texture ของ pack เอง ไม่พึ่ง vanilla)

นอกจาก `cnpc` ยังมี**โมเดล NPC สวย ๆ อีก 29 ตัว** (แปลงมาจาก Blockbench/Model Engine
ของ Java Edition) — spawn ด้วยชื่อสั้นได้เลย มี autocomplete:

**NPC ที่มี animation (เล่นท่าทางได้เมื่อคลิก):**

`adventurer`, `archer`, `blacksmith`, `butcher`, `dworf`, `farmer`,
`farmermaxvers`, `guard`, `guardcyan`, `guardgreen`, `guardorange`,
`guardparts`, `guardpink`, `guardpurple`, `guardred`, `guardyellow`,
`king`, `kingdom_guardian`, `mageshaman`, `miner`, `pirate`, `tavern`, `wizard`

**ของตกแต่ง (ไม่มี animation):**

`anchor`, `lootbag`, `minecart`, `npcgreeting`, `tap`, `throne`

```
/npc create king พระราชา
/npc create pirate กัปตัน
/npc animations set 1 greet
```

**วิธีติดตั้ง pack บน server (BDS/Endstone):**

1. copy `addon/NPCPack_BP` ไปที่ `development_behavior_packs/` และ
   `addon/NPCPack_RP` ไปที่ `development_resource_packs/` ของ server
2. เพิ่มในไฟล์ `worlds/<ชื่อโลก>/world_behavior_packs.json`:
   ```json
   [{"pack_id": "3027883a-3b9b-4f42-8419-f378cd4b8007", "version": [1, 3, 0]}]
   ```
   และ `worlds/<ชื่อโลก>/world_resource_packs.json`:
   ```json
   [{"pack_id": "f3ac6d21-db6e-41dc-ae09-46210f330b12", "version": [1, 3, 0]}]
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
/npc create king พระราชา
→ สร้าง NPC สำเร็จ! id: 1

/npc look 1
→ NPC หันหน้ามองผู้เล่นที่เข้ามาใกล้

/npc animations set 1 greet
→ ตั้ง animation 'greet' เมื่อคลิก

/npc command add 1 console:give {player} bread 5
/npc command add 1 console:tell {player} รับขนมปังไปกินนะ!
```

จากนั้นผู้เล่นคนไหนเข้าใกล้ NPC → NPC หันมามอง, คลิก → เล่นท่า greet พร้อมได้ขนมปัง 5 ก้อนและข้อความ

## Config (`plugins/NPCPlugin/config.toml` — สร้างอัตโนมัติครั้งแรก)

```toml
default_run_as = "console"   # ผู้รัน default เมื่อไม่ใส่ prefix: console | player
freeze_interval_ticks = 20   # ความถี่เช็คตำแหน่ง/respawn (20 = 1 วินาที)
interact_cooldown = 0.5      # วินาทีขั้นต่ำระหว่างคลิกของผู้เล่นคนเดิม (กัน event ยิงซ้ำ)
look_at_range = 3.0          # ระยะเริ่มต้นเมื่อเปิด /npc look โดยไม่ระบุระยะ
debug = false                # log การคลิก/ตี NPC ไว้ไล่ปัญหา (เปิดเฉพาะตอนจำเป็น)
```

ข้อมูล NPC เก็บที่ `plugins/NPCPlugin/npcs.json` — แก้มือได้ตอน server ปิด

ข้อมูล animation ของ NPC แต่ละ type เก็บที่ `plugins/NPCPlugin/npc_animations.json`
(สร้างอัตโนมัติจาก `tools/bbmodel2bedrock.py`) — สั่ง `/npc reload` เพื่อโหลดใหม่

## หลักการทำงาน (สำหรับคนอยากแก้โค้ด)

- **ระบุตัว NPC:** entity ทุกตัวถูกติด scoreboard tag `npcp:<id>` เพราะ runtime id
  ของ entity เปลี่ยนทุกครั้งที่ restart — tag + `npcs.json` คือ source of truth
- **ยืนอยู่กับที่:** ใส่ effect slowness 255 ซ้ำทุกรอบ (ผ่าน tag รวม `npcp_all`) +
  scheduler task ทุก `freeze_interval_ticks` เช็คว่า NPC ขยับเกิน 0.2 บล็อกหรือไม่
  ถ้าใช่ teleport กลับ
- **หันหน้ามองผู้เล่น:** เปิดเฉพาะตัวด้วย `/npc look <id> [range]` — ใน freeze_tick
  สแกนผู้เล่นออนไลน์ หาคนที่ใกล้ที่สุดในระยะที่ตั้งไว้ แล้วคำนวณ yaw/pitch หมุน NPC ไปหา
  ถ้าไม่มีผู้เล่นในระยะ NPC จะหันกลับทิศทางเดิม
- **อมตะ:** cancel `ActorDamageEvent` และ `ActorKnockbackEvent` ของ NPC ทุกตัว —
  ตีไม่ตาย ไม่กระเด็น (ต่อให้ตายด้วย /kill ก็เกิดใหม่เองใน 1 วินาที)
- **ไม่ despawn:** task เดียวกันเช็คว่า entity ยังอยู่ไหม ถ้าหาย (despawn/ตาย/หลัง restart)
  จะ spawn ใหม่จากข้อมูลใน JSON ทันทีที่ chunk นั้นโหลด
- **การคลิก:** ใช้ `PlayerInteractActorEvent` — เจอ tag ของปลั๊กอินก็ cancel event
  (กันหน้าต่าง trade/UI เปิด) แล้วเล่น animation (ถ้าตั้งไว้) และรัน command ที่ผูกไว้
- **Animation:** เก็บชื่อ animation สั้นใน record (`npcs.json`) เมื่อคลิกจะสั่ง
  `/playanimation @e[tag=npcp:<id>] animation.npcp_<type>.<action>`

## Checklist ทดสอบ

1. `/npc create npc ทดสอบ` → NPC โผล่ที่ตำแหน่งเรา มีชื่อเหนือหัว
2. ตี NPC → ไม่เสียเลือด ไม่กระเด็น ไม่ตาย และไม่เดินหนีออกจากจุดเดิม
3. `/npc look 1` แล้วเดินเข้าใกล้ NPC ในระยะ 3 บล็อก → NPC หันหน้ามองเรา, เดินออกไป → หันกลับทิศเดิม
4. `/npc command add 1 console:say {player} คลิกฉัน!` แล้วคลิก NPC → ข้อความขึ้น
5. `/npc command add 1 player:me กำลังคุยกับ NPC` แล้วคลิก → รันในนามผู้เล่น
6. `/npc list` → เห็น NPC พร้อมจำนวน command
7. `/npc setname 1 ชื่อใหม่` → ชื่อเหนือหัวเปลี่ยนทันที
8. `/npc create king ราชา` แล้ว `/npc animations set 2` → เห็นรายการ animation
9. `/npc animations set 2 greet` แล้วคลิก NPC → เห็น animation เล่น
10. `/npc animations remove 2` → ลบ animation แล้ว คลิกไม่เล่นท่าอีก
11. restart server → NPC กลับมาที่เดิมพร้อม command + animation ครบ
12. `/npc reload` → config + animation data โหลดใหม่โดยไม่ต้อง restart
13. `/npc remove 1` → NPC หายและไม่กลับมาอีก
