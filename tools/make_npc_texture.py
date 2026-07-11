"""สร้าง texture 64x64 สำหรับ npcp:npc (layout แบบ skin humanoid มาตรฐาน)"""
import struct
import zlib
import sys

W = H = 64
SKIN = (240, 200, 160, 255)       # ผิว
SKIN_D = (215, 175, 135, 255)     # ผิวเข้ม (จมูก)
HAIR = (70, 45, 25, 255)          # ผม
EYE = (60, 60, 90, 255)           # ตา
EYE_W = (255, 255, 255, 255)      # ตาขาว
MOUTH = (170, 120, 90, 255)       # ปาก
ROBE = (122, 82, 48, 255)         # เสื้อคลุมน้ำตาล
ROBE_D = (95, 62, 34, 255)        # เข็มขัด/ขา
CLEAR = (0, 0, 0, 0)

px = [[CLEAR for _ in range(W)] for _ in range(H)]


def fill(x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px[y][x] = c


# ---- หัว (uv 0,0 ครอบ x0-31 y0-15) ----
fill(0, 0, 31, 15, SKIN)
fill(8, 0, 23, 7, HAIR)          # top ของหัว = ผม
fill(0, 8, 31, 9, HAIR)          # แนวผมรอบหัวด้านบน
fill(24, 8, 31, 15, HAIR)        # back ของหัว = ผมทั้งแผ่น
# หน้า (x8-15 y8-15)
fill(9, 11, 9, 11, EYE_W)
fill(10, 11, 10, 11, EYE)
fill(14, 11, 14, 11, EYE_W)
fill(13, 11, 13, 11, EYE)
fill(11, 12, 12, 13, SKIN_D)     # จมูก
fill(11, 14, 12, 14, MOUTH)      # ปาก

# ---- ตัว (uv 16,16 ครอบ x16-39 y16-31) ----
fill(16, 16, 39, 31, ROBE)
fill(16, 26, 39, 27, ROBE_D)     # เข็มขัด

# ---- แขนขวา (uv 40,16) ----
fill(40, 16, 55, 31, ROBE)
fill(40, 29, 55, 31, SKIN)       # มือ

# ---- ขาขวา (uv 0,16) ----
fill(0, 16, 15, 31, ROBE_D)

# ---- แขนซ้าย (uv 32,48) ----
fill(32, 48, 47, 63, ROBE)
fill(32, 61, 47, 63, SKIN)       # มือ

# ---- ขาซ้าย (uv 16,48) ----
fill(16, 48, 31, 63, ROBE_D)


def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)
png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9))
       + chunk(b"IEND", b""))

with open(sys.argv[1], "wb") as f:
    f.write(png)
print("wrote", sys.argv[1], len(png), "bytes")
