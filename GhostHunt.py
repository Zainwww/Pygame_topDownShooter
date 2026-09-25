"""
GUNT
-------------------
Game survival horror top-down berdasarkan GDD:
- Player terjebak di dalam hutan, harus membasmi hantu yang terus bertambah.
- Senjata random di lantai (pistol, rifle, machine gun, shotgun), maks 3 sekaligus.
- Hantu selalu mengejar player; makin banyak dibunuh, makin banyak & makin kuat yang spawn.
- Visi player terbatas (fog of war). Layar memerah saat kena hit, hantu berkedip merah saat kena tembak.
- Tidak ada batas waktu -- game berjalan sampai HP player habis.

Kontrol:
  WASD / Panah  -> bergerak
  Klik kiri     -> tembak (ke arah kursor)
  F11           -> toggle fullscreen
  R             -> main lagi (saat game over)
  ESC           -> keluar fullscreen, atau keluar game (saat windowed)
"""

import pygame
import random
import math
import sys
import os

# ----------------------------------------------------------------------------
# Konfigurasi & konstanta
# ----------------------------------------------------------------------------
TILE = 32
GRID_W, GRID_H = 44, 30
MAP_W, MAP_H = GRID_W * TILE, GRID_H * TILE
SCREEN_W, SCREEN_H = MAP_W, MAP_H
FPS = 60

BLACK = (10, 10, 14)
GRASS_COLORS = [(34, 84, 42), (31, 78, 40), (38, 90, 46), (29, 72, 37)]
TREE_TRUNK = (70, 45, 25)
TREE_CANOPY_DARK = (22, 66, 32)
TREE_CANOPY = (33, 92, 44)
TREE_CANOPY_LIGHT = (54, 118, 58)
WHITE = (235, 235, 235)
RED = (205, 40, 40)
GREEN = (60, 200, 90)
YELLOW = (230, 200, 60)
GHOST_COLOR = (210, 215, 225)
PLAYER_COLOR = (70, 150, 230)


# ----------------------------------------------------------------------------
# Sprite kustom (OPSIONAL) -- di sinilah kamu pasang gambar sendiri.
#
# Cara pakai:
#   1. Taruh file gambar (.png disarankan, transparan) di folder SPRITE_DIR.
#   2. Isi path-nya di bawah, misalnya:
#        PLAYER_SPRITE_PATH = os.path.join(SPRITE_DIR, "player.png")
#        GHOST_SPRITE_PATHS["FastGhost"] = os.path.join(SPRITE_DIR, "ghost_fast.png")
#   3. Kalau path masih None atau filenya tidak ada, game otomatis balik ke
#      gambar bawaan (lingkaran/vector) -- tidak akan error/crash.
#
# Catatan orientasi: sprite PLAYER sebaiknya digambar menghadap KANAN,
# karena akan diputar otomatis mengikuti arah tembak/kursor.
# ----------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SPRITE_DIR = os.path.join(BASE_DIR, "sprite")

PLAYER_SPRITE_PATH = None
PLAYER_SPRITE_SIZE = (48, 48)

GHOST_SPRITE_PATHS = {
    "Ghost": os.path.join(SPRITE_DIR, "normal.png"),          # hantu normal
    "FastGhost": os.path.join(SPRITE_DIR, "speed.png"),     # hantu cepat
    "DasherGhost": os.path.join(SPRITE_DIR, "dash.png"),    # hantu dash
    "PoisonGhost": os.path.join(SPRITE_DIR, "poison.png"),     # hantu racun
}
GHOST_SPRITE_SIZE = (42, 42)

WEAPON_SPRITE_PATHS = {
    "Pistol": None,
    "Rifle": None,
    "MachineGun": None,
    "Shotgun": None,
}
WEAPON_ICON_SIZE = (26, 26)


def load_sprite(path, size=None):
    """Muat 1 file gambar jadi pygame Surface. Aman dipanggil kapan pun --
    kalau path kosong / file tidak ada / gagal dibaca, cukup return None
    (pemanggilnya lalu otomatis pakai gambar bawaan, tidak akan crash)."""
    if not path:
        return None
    if not os.path.isfile(path):
        print(f"[sprite] File tidak ditemukan, pakai gambar bawaan: {path}")
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        return img
    except Exception as e:
        print(f"[sprite] Gagal memuat '{path}': {e}")
        return None


# ----------------------------------------------------------------------------
# Senjata (OOP: base class + subclass per jenis senjata)
# ----------------------------------------------------------------------------
class WeaponType:
    name = "Weapon"
    damage = 10
    cooldown = 400      # ms antar tembakan
    bullet_speed = 9
    pellets = 1          # jumlah peluru per tembakan (shotgun > 1)
    spread = 0.03         # radian, akurasi
    bullet_radius = 4
    range_ms = 900        # umur peluru sebelum hilang
    color = WHITE
    max_ammo = 12          # kapasitas amunisi, beda-beda tiap jenis senjata
    rarity = "Umum"
    rarity_color = (190, 190, 195)
    drop_weight = 50        # bobot kemunculan saat gacha (makin besar makin sering)

    def __init__(self):
        self.ammo = self.max_ammo   # tiap instance senjata punya amunisi sendiri


class Pistol(WeaponType):
    name = "Pistol"
    damage = 18
    cooldown = 320
    bullet_speed = 10
    spread = 0.03
    bullet_radius = 4
    color = (225, 225, 230)
    max_ammo = 15
    rarity = "Umum"
    rarity_color = (190, 190, 195)
    drop_weight = 50


class Rifle(WeaponType):
    name = "Rifle"
    damage = 26
    cooldown = 190
    bullet_speed = 14
    spread = 0.02
    bullet_radius = 4
    range_ms = 1100
    color = (120, 200, 255)
    max_ammo = 20
    rarity = "Legendaris"
    rarity_color = (235, 180, 60)
    drop_weight = 7


class MachineGun(WeaponType):
    name = "Machine Gun"
    damage = 9
    cooldown = 90
    bullet_speed = 12
    spread = 0.14
    bullet_radius = 3
    color = (255, 200, 90)
    max_ammo = 60
    rarity = "Jarang"
    rarity_color = (90, 170, 230)
    drop_weight = 27


class Shotgun(WeaponType):
    name = "Shotgun"
    damage = 8
    cooldown = 650
    bullet_speed = 11
    pellets = 6
    spread = 0.5
    bullet_radius = 3
    range_ms = 500
    color = (255, 120, 90)
    max_ammo = 10
    rarity = "Epik"
    rarity_color = (170, 90, 220)
    drop_weight = 16


WEAPON_TYPES = [Pistol, Rifle, MachineGun, Shotgun]


# ----------------------------------------------------------------------------
# Map hutan (di-generate prosedural: gerombolan pohon + pohon liar tersebar)
# "#" = pohon/penghalang (juga jadi batas luar hutan), "." = rumput terbuka
# ----------------------------------------------------------------------------
class GameMap:
    def __init__(self):
        self.grid = [["."] * GRID_W for _ in range(GRID_H)]
        for _ in range(12):
            self._generate()
            reachable = self._connected_floor()
            if len(reachable) >= (GRID_W - 2) * (GRID_H - 2) * 0.4:
                break
        self.floor_tiles = list(reachable)

    def _generate(self):
        # reset ke rumput terbuka
        for r in range(GRID_H):
            for c in range(GRID_W):
                self.grid[r][c] = "."

        # batas hutan mengelilingi peta -- player terjebak di dalamnya
        for c in range(GRID_W):
            self.grid[0][c] = "#"
            self.grid[GRID_H - 1][c] = "#"
        for r in range(GRID_H):
            self.grid[r][0] = "#"
            self.grid[r][GRID_W - 1] = "#"

        # gerombolan pohon ditempatkan per-sektor (grid sektor menutupi seluruh
        # peta) supaya persebarannya rata, bukan menumpuk di satu sisi saja
        sector_size = 8
        cols = max(1, (GRID_W - 2) // sector_size)
        rows = max(1, (GRID_H - 2) // sector_size)
        for sr in range(rows):
            for sc in range(cols):
                if random.random() < 0.85:   # sedikit sektor dibiarkan kosong biar variatif
                    x0 = 1 + sc * sector_size
                    y0 = 1 + sr * sector_size
                    x1 = min(GRID_W - 2, x0 + sector_size - 1)
                    y1 = min(GRID_H - 2, y0 + sector_size - 1)
                    cx = random.randint(x0, x1)
                    cy = random.randint(y0, y1)
                    radius = random.randint(2, 3)
                    density = random.uniform(0.22, 0.38)
                    for r in range(cy - radius, cy + radius + 1):
                        for c in range(cx - radius, cx + radius + 1):
                            if 1 <= c < GRID_W - 1 and 1 <= r < GRID_H - 1:
                                if math.hypot(c - cx, r - cy) <= radius and random.random() < density:
                                    self.grid[r][c] = "#"

        # pohon liar tunggal tersebar acak merata di seluruh peta untuk variasi
        for r in range(1, GRID_H - 1):
            for c in range(1, GRID_W - 1):
                if self.grid[r][c] == "." and random.random() < 0.008:
                    self.grid[r][c] = "#"

    def _connected_floor(self):
        # BFS 4-arah, ambil komponen rumput terhubung terbesar supaya semua
        # titik spawn (player/hantu/senjata) dijamin bisa dijangkau
        all_floor = {
            (c, r) for r in range(GRID_H) for c in range(GRID_W)
            if self.grid[r][c] == "."
        }
        visited, best = set(), set()
        for start in all_floor:
            if start in visited:
                continue
            comp, stack = set(), [start]
            visited.add(start)
            while stack:
                c, r = stack.pop()
                comp.add((c, r))
                for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nxt = (c + dc, r + dr)
                    if nxt in all_floor and nxt not in visited:
                        visited.add(nxt)
                        stack.append(nxt)
            if len(comp) > len(best):
                best = comp
        return best

    def is_wall(self, col, row):
        if col < 0 or col >= GRID_W or row < 0 or row >= GRID_H:
            return True
        return self.grid[row][col] == "#"

    def rect_collides(self, rect):
        left = rect.left // TILE
        right = (rect.right - 1) // TILE
        top = rect.top // TILE
        bottom = (rect.bottom - 1) // TILE
        for r in range(top, bottom + 1):
            for c in range(left, right + 1):
                if self.is_wall(c, r):
                    return True
        return False

    def random_floor_pos(self, exclude_center=None, min_dist=0):
        for _ in range(200):
            c, r = random.choice(self.floor_tiles)
            x, y = c * TILE + TILE / 2, r * TILE + TILE / 2
            if exclude_center and math.hypot(x - exclude_center[0], y - exclude_center[1]) < min_dist:
                continue
            return x, y
        c, r = random.choice(self.floor_tiles)
        return c * TILE + TILE / 2, r * TILE + TILE / 2

    def draw(self, surf):
        for r in range(GRID_H):
            for c in range(GRID_W):
                rect = pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                grass = GRASS_COLORS[(c * 7 + r * 13) % len(GRASS_COLORS)]
                pygame.draw.rect(surf, grass, rect)
                if self.grid[r][c] == "#":
                    self._draw_tree(surf, rect)

    @staticmethod
    def _draw_tree(surf, rect):
        cx, cy = rect.center
        pygame.draw.rect(surf, TREE_TRUNK, (cx - 3, cy - 2, 6, 13))
        pygame.draw.circle(surf, TREE_CANOPY_DARK, (cx, cy - 8), 15)
        pygame.draw.circle(surf, TREE_CANOPY, (cx - 4, cy - 11), 12)
        pygame.draw.circle(surf, TREE_CANOPY_LIGHT, (cx + 3, cy - 14), 7)


# ----------------------------------------------------------------------------
# Peluru
# ----------------------------------------------------------------------------
class Bullet:
    def __init__(self, pos, angle, weapon):
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(math.cos(angle), math.sin(angle)) * weapon.bullet_speed
        self.damage = weapon.damage
        self.color = weapon.color
        self.radius = weapon.bullet_radius
        self.born = pygame.time.get_ticks()
        self.life = weapon.range_ms
        self.alive = True

    def update(self):
        self.pos += self.vel
        if pygame.time.get_ticks() - self.born > self.life:
            self.alive = False
            return
        if 0 <= self.pos.x < MAP_W and 0 <= self.pos.y < MAP_H:
            col, row = int(self.pos.x // TILE), int(self.pos.y // TILE)
            if game_map_is_wall_cache.is_wall(col, row):
                self.alive = False
        else:
            self.alive = False

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)

    def get_rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                            self.radius * 2, self.radius * 2)


# helper module-level reference so Bullet.update can reach the active map
# (diset oleh Game saat reset, menghindari harus lempar map ke tiap update call)
game_map_is_wall_cache = None


# ----------------------------------------------------------------------------
# Peti senjata (chest) -- isinya rahasia, ditentukan lewat gacha saat dibuka
# ----------------------------------------------------------------------------
class WeaponChest:
    def __init__(self, pos):
        self.pos = pygame.math.Vector2(pos)
        self.radius = 13
        self.bob = random.random() * math.tau
        self.opened = False   # ditandai True sesaat sebelum dihapus dari list

    def update(self, dt):
        self.bob += dt * 0.003

    def draw(self, surf):
        offset = math.sin(self.bob) * 2
        rect = pygame.Rect(0, 0, 26, 20)
        rect.center = (int(self.pos.x), int(self.pos.y + offset))
        pygame.draw.rect(surf, (120, 82, 42), rect, border_radius=3)
        pygame.draw.rect(surf, (75, 48, 22), rect, 2, border_radius=3)
        pygame.draw.line(surf, (75, 48, 22), (rect.left + 2, rect.centery), (rect.right - 2, rect.centery), 3)
        pygame.draw.circle(surf, (235, 205, 90), rect.center, 3)
        pygame.draw.circle(surf, (120, 82, 42), rect.center, 3, 1)

    def get_rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                            self.radius * 2, self.radius * 2)


# ----------------------------------------------------------------------------
# Player
# ----------------------------------------------------------------------------
class Player:
    def __init__(self, pos):
        self.pos = pygame.math.Vector2(pos)
        self.radius = 12
        self.speed = 3.4
        self.max_hp = 100
        self.hp = self.max_hp
        self.weapon = Pistol()
        self.last_shot = 0
        self.hit_flash = 0
        self.vision_radius = 190
        self.angle = 0.0
        self.poison_time = 0
        self.poison_next_tick = 0
        self.poison_dps = 0
        self.empty_flash = 0   # kedip peringatan saat amunisi habis

        # Dash player
        self.max_stamina = 100
        self.stamina = self.max_stamina
        self.stamina_cost = 50
        self.stamina_regen = 25.0       # stamina per detik
        self.last_direction = pygame.math.Vector2(1, 0)
        self.dash_direction = pygame.math.Vector2(0, 0)
        self.dash_speed = 9.0
        self.dash_duration = 180
        self.dash_timer = 0
        self.is_dashing = False

    def get_rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                            self.radius * 2, self.radius * 2)

    def handle_input(self, keys, game_map):
        move = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1

        if move.length_squared() > 0:
            self.last_direction = move.normalize()
            move = self.last_direction * self.speed

        if not self.is_dashing:
            self._move(move, game_map)

    def try_dash(self, game_map):
        if self.is_dashing or self.stamina < self.stamina_cost:
            return False

        self.stamina -= self.stamina_cost
        self.dash_direction = self.last_direction.copy()
        self.dash_timer = self.dash_duration
        self.is_dashing = True
        return True

    def _update_dash(self, dt, game_map):
        if not self.is_dashing:
            self.stamina = min(
                self.max_stamina,
                self.stamina + self.stamina_regen * (dt / 1000.0)
            )
            return

        dash_step = self.dash_direction * self.dash_speed * (dt / 16.6667)
        self._move(dash_step, game_map)
        self.dash_timer -= dt

        if self.dash_timer <= 0:
            self.dash_timer = 0
            self.is_dashing = False

    def _move(self, move, game_map):
        # gerak per-sumbu supaya bisa "meluncur" di sepanjang tembok
        self.pos.x += move.x
        if game_map.rect_collides(self.get_rect()):
            self.pos.x -= move.x
        self.pos.y += move.y
        if game_map.rect_collides(self.get_rect()):
            self.pos.y -= move.y

    def aim(self, mouse_pos):
        dx = mouse_pos[0] - self.pos.x
        dy = mouse_pos[1] - self.pos.y
        self.angle = math.atan2(dy, dx)

    def try_shoot(self, now):
        if now - self.last_shot < self.weapon.cooldown:
            return []
        if self.weapon.ammo <= 0:
            self.empty_flash = 260   # amunisi habis -- tidak bisa nembak
            return []
        self.last_shot = now
        self.weapon.ammo -= 1
        bullets = []
        for _ in range(self.weapon.pellets):
            spread = random.uniform(-self.weapon.spread, self.weapon.spread)
            bullets.append(Bullet(self.pos, self.angle + spread, self.weapon))
        return bullets

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 260

    def apply_poison(self, duration_ms, dps):
        # racun bisa ditumpuk durasinya (tidak reset tick yang sedang berjalan)
        self.poison_time = max(self.poison_time, duration_ms)
        self.poison_dps = max(self.poison_dps, dps)
        if self.poison_next_tick <= 0:
            self.poison_next_tick = 500

    def update(self, dt, game_map):
        self._update_dash(dt, game_map)
        if self.hit_flash > 0:
            self.hit_flash -= dt
        if self.empty_flash > 0:
            self.empty_flash -= dt
        if self.poison_time > 0:
            self.poison_time = max(0, self.poison_time - dt)
            self.poison_next_tick -= dt
            if self.poison_next_tick <= 0:
                self.poison_next_tick = 500
                self.hp = max(0, self.hp - self.poison_dps)
            if self.poison_time <= 0:
                self.poison_dps = 0

    def draw(self, surf, sprite=None):
        if self.poison_time > 0:
            pulse = 3 + int(2 * math.sin(pygame.time.get_ticks() * 0.012))
            pygame.draw.circle(surf, (110, 210, 90),
                                (int(self.pos.x), int(self.pos.y)), self.radius + 5 + pulse, 2)
        if sprite:
            # sprite digambar menghadap kanan secara default, diputar sesuai arah bidik
            rotated = pygame.transform.rotate(sprite, -math.degrees(self.angle))
            rect = rotated.get_rect(center=(int(self.pos.x), int(self.pos.y)))
            surf.blit(rotated, rect)
        else:
            pygame.draw.circle(surf, PLAYER_COLOR, (int(self.pos.x), int(self.pos.y)), self.radius)
            pygame.draw.circle(surf, (20, 30, 45), (int(self.pos.x), int(self.pos.y)), self.radius, 2)
            tip = self.pos + pygame.math.Vector2(math.cos(self.angle), math.sin(self.angle)) * (self.radius + 9)
            pygame.draw.line(surf, WHITE, self.pos, tip, 3)


# ----------------------------------------------------------------------------
# Proyektil racun (ditembakkan oleh PoisonGhost)
# ----------------------------------------------------------------------------
class PoisonBolt:
    speed = 4.6
    damage = 6
    poison_dps = 3
    poison_duration = 3000
    radius = 7
    life_ms = 3000
    color = (120, 210, 90)

    def __init__(self, pos, angle):
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(math.cos(angle), math.sin(angle)) * self.speed
        self.born = pygame.time.get_ticks()
        self.alive = True

    def update(self, game_map):
        self.pos += self.vel
        if pygame.time.get_ticks() - self.born > self.life_ms:
            self.alive = False
            return
        if 0 <= self.pos.x < MAP_W and 0 <= self.pos.y < MAP_H:
            col, row = int(self.pos.x // TILE), int(self.pos.y // TILE)
            if game_map.is_wall(col, row):
                self.alive = False
        else:
            self.alive = False

    def draw(self, surf):
        pulse = 2 if (pygame.time.get_ticks() // 100) % 2 == 0 else 0
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), self.radius + pulse)
        pygame.draw.circle(surf, (55, 130, 40), (int(self.pos.x), int(self.pos.y)), self.radius + pulse, 1)

    def get_rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                            self.radius * 2, self.radius * 2)


# ----------------------------------------------------------------------------
# Hantu (OOP: base class + subclass per jenis perilaku, mirip pola WeaponType)
# ----------------------------------------------------------------------------
class Ghost:
    """Hantu normal: mengejar player lurus dengan kecepatan tetap."""
    type_name = "Hantu"
    speed_mult = 1.0
    hp_mult = 1.0
    contact_damage = 12
    color = GHOST_COLOR

    def __init__(self, pos, hp, speed):
        self.pos = pygame.math.Vector2(pos)
        self.radius = 13
        self.max_hp = hp
        self.hp = hp
        self.speed = speed
        self.flash = 0
        self.contact_cd = 0
        self.alive = True

    def get_rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                            self.radius * 2, self.radius * 2)

    def _step(self, move, game_map):
        # gerak dengan slide di sepanjang pohon/tembok (per-sumbu)
        old = pygame.math.Vector2(self.pos)
        self.pos += move
        if game_map.rect_collides(self.get_rect()):
            self.pos = pygame.math.Vector2(old)
            self.pos.x += move.x
            if game_map.rect_collides(self.get_rect()):
                self.pos.x = old.x
            self.pos.y += move.y
            if game_map.rect_collides(self.get_rect()):
                self.pos.y = old.y

    def _tick_timers(self, dt):
        if self.flash > 0:
            self.flash -= dt
        if self.contact_cd > 0:
            self.contact_cd -= dt

    def update(self, dt, player, game_map):
        direction = player.pos - self.pos
        if direction.length_squared() > 1:
            direction = direction.normalize() * self.speed
        else:
            direction = pygame.math.Vector2(0, 0)
        self._step(direction, game_map)
        self._tick_timers(dt)
        return []   # subclass ranged bisa mengembalikan proyektil baru di sini

    def take_damage(self, amount):
        self.hp -= amount
        self.flash = 150
        if self.hp <= 0:
            self.alive = False

    def _body_color(self):
        if self.flash > 0:
            t = min(1.0, self.flash / 150)
            return tuple(int(self.color[i] * (1 - t) + RED[i] * t) for i in range(3))
        return self.color

    def _overlay_tint(self):
        """Warna kedip translucent di atas sprite (dipakai saat mode sprite aktif).
        Return None kalau tidak perlu kedip apa-apa saat ini."""
        if self.flash > 0:
            t = min(1.0, self.flash / 150)
            return (255, 60, 60), int(170 * t)
        return None

    def draw(self, surf, sprite=None):
        if sprite:
            rect = sprite.get_rect(center=(int(self.pos.x), int(self.pos.y)))
            surf.blit(sprite, rect)
            tint = self._overlay_tint()
            if tint:
                (r, g, b), alpha = tint
                overlay = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
                pygame.draw.circle(overlay, (r, g, b, alpha),
                                    (sprite.get_width() // 2, sprite.get_height() // 2),
                                    min(sprite.get_size()) // 2)
                surf.blit(overlay, rect)
        else:
            color = self._body_color()
            pygame.draw.circle(surf, color, (int(self.pos.x), int(self.pos.y)), self.radius)
            pygame.draw.circle(surf, (35, 35, 45), (int(self.pos.x - 5), int(self.pos.y - 3)), 2)
            pygame.draw.circle(surf, (35, 35, 45), (int(self.pos.x + 5), int(self.pos.y - 3)), 2)
        if self.hp < self.max_hp:
            w = 26
            x, y = self.pos.x - w / 2, self.pos.y - self.radius - 10
            pygame.draw.rect(surf, (50, 10, 10), (x, y, w, 4))
            pygame.draw.rect(surf, GREEN, (x, y, w * max(0, self.hp / self.max_hp), 4))


class FastGhost(Ghost):
    """Hantu lari cepat: HP lebih rendah, tapi jauh lebih kencang mengejar."""
    type_name = "Hantu Cepat"
    speed_mult = 1.9
    hp_mult = 0.7
    contact_damage = 10
    color = (235, 160, 60)


class DasherGhost(Ghost):
    """Hantu dash: mengejar normal, lalu berhenti sejenak (kedip putih) sebelum menerjang cepat."""
    type_name = "Hantu Dash"
    speed_mult = 1.0
    hp_mult = 1.0
    contact_damage = 16
    color = (190, 120, 230)

    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed)
        self.base_speed = speed
        self.dash_state = "chase"   # chase -> telegraph -> dash -> cooldown
        self.dash_timer = random.randint(1200, 2200)
        self.dash_dir = pygame.math.Vector2(0, 0)

    def update(self, dt, player, game_map):
        self.dash_timer -= dt

        if self.dash_state == "chase":
            direction = player.pos - self.pos
            if direction.length_squared() > 1:
                direction = direction.normalize() * self.base_speed
            else:
                direction = pygame.math.Vector2(0, 0)
            self._step(direction, game_map)
            if self.dash_timer <= 0:
                self.dash_state = "telegraph"
                self.dash_timer = 350

        elif self.dash_state == "telegraph":
            if self.dash_timer <= 0:
                to_player = player.pos - self.pos
                self.dash_dir = to_player.normalize() if to_player.length_squared() > 1 \
                    else pygame.math.Vector2(1, 0)
                self.dash_state = "dash"
                self.dash_timer = 260

        elif self.dash_state == "dash":
            self._step(self.dash_dir * self.base_speed * 4.2, game_map)
            if self.dash_timer <= 0:
                self.dash_state = "cooldown"
                self.dash_timer = 1400

        elif self.dash_state == "cooldown":
            direction = player.pos - self.pos
            if direction.length_squared() > 1:
                direction = direction.normalize() * self.base_speed * 0.6
            else:
                direction = pygame.math.Vector2(0, 0)
            self._step(direction, game_map)
            if self.dash_timer <= 0:
                self.dash_state = "chase"
                self.dash_timer = random.randint(1800, 2800)

        self._tick_timers(dt)
        return []

    def _body_color(self):
        if self.dash_state == "telegraph":
            pulse = 255 if (pygame.time.get_ticks() // 80) % 2 == 0 else 150
            return (pulse, pulse, 255)
        return super()._body_color()

    def _overlay_tint(self):
        if self.dash_state == "telegraph":
            pulse = 255 if (pygame.time.get_ticks() // 80) % 2 == 0 else 140
            return (pulse, pulse, 255), 190
        return super()._overlay_tint()


class PoisonGhost(Ghost):
    """Hantu penyembur racun: jaga jarak lalu menembakkan proyektil racun ke player."""
    type_name = "Hantu Racun"
    speed_mult = 0.65
    hp_mult = 1.1
    contact_damage = 8
    color = (120, 200, 90)
    attack_range = 340
    fire_cooldown = 1900

    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed)
        self.fire_timer = random.randint(400, 1200)

    def update(self, dt, player, game_map):
        to_player = player.pos - self.pos
        dist = to_player.length()
        direction = to_player.normalize() if dist > 1 else pygame.math.Vector2(0, 0)

        if dist > self.attack_range:
            move = direction * self.speed
        elif dist < self.attack_range * 0.55:
            move = -direction * self.speed * 0.7   # mundur jaga jarak
        else:
            move = pygame.math.Vector2(0, 0)         # diam & menyembur

        self._step(move, game_map)
        self._tick_timers(dt)

        self.fire_timer -= dt
        spawned = []
        if dist <= self.attack_range and self.fire_timer <= 0:
            self.fire_timer = self.fire_cooldown
            angle = math.atan2(to_player.y, to_player.x)
            spawned.append(PoisonBolt(self.pos, angle))
        return spawned


GHOST_TYPES = [Ghost, FastGhost, DasherGhost, PoisonGhost]


# ----------------------------------------------------------------------------
# Fog of war helper
# ----------------------------------------------------------------------------
def make_light_mask(radius, steps=24):
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for k in range(steps, 0, -1):
        r = int(radius * k / steps)
        alpha = int(255 * (steps - k) / steps)
        pygame.draw.circle(surf, (0, 0, 0, alpha), (radius, radius), r)
    return surf


# ----------------------------------------------------------------------------
# Game utama
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        # game_surface = kanvas logis tetap (SCREEN_W x SCREEN_H) tempat semua
        # digambar; self.screen = jendela OS sesungguhnya, bisa windowed atau
        # fullscreen dengan ukuran berapa pun -- game_surface di-scale ke situ
        # tiap frame (letterbox), jadi logika game tidak perlu tahu soal ukuran layar.
        self.game_surface = pygame.Surface((SCREEN_W, SCREEN_H))
        self.fullscreen = True
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.render_scale = 1.0
        self.render_offset = (0, 0)
        pygame.display.set_caption("GUNT")
        self._lock_mouse()   # sembunyikan kursor OS & kunci mouse di dalam window
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("arial", 46, bold=True)
        self.font = pygame.font.SysFont("arial", 22)
        self.font_small = pygame.font.SysFont("arial", 16)
        self.light_mask = make_light_mask(190)

        # muat sprite kustom (kalau ada) sekali di awal -- lihat konfigurasi
        # PLAYER_SPRITE_PATH / GHOST_SPRITE_PATHS / WEAPON_SPRITE_PATHS di atas
        self.player_sprite = load_sprite(PLAYER_SPRITE_PATH, PLAYER_SPRITE_SIZE)
        self.ghost_sprites = {
            name: load_sprite(path, GHOST_SPRITE_SIZE)
            for name, path in GHOST_SPRITE_PATHS.items()
        }
        self.weapon_icons = {
            name: load_sprite(path, WEAPON_ICON_SIZE)
            for name, path in WEAPON_SPRITE_PATHS.items()
        }

        self.state = "MENU"
        self.map = None
        self.player = None
        self.bullets = []
        self.ghosts = []
        self.chests = []
        self.poison_bolts = []
        self.kills = 0
        self.score = 0
        self.ghost_spawn_timer = 0
        self.chest_spawn_timer = 0
        self.gacha_banner = None   # {"text","color","icon","timer"} -- hasil akhir gacha, sesaat setelah spin berhenti
        self.gacha_spin = None      # {"reel","win_index","won_cls","elapsed","duration","item_w"} -- lagi muter

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        self._lock_mouse()   # set_mode baru bisa reset status grab/cursor, pasang ulang

    def resize_window(self, size):
        if not self.fullscreen:
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            self._lock_mouse()

    def _lock_mouse(self):
        # kursor asli disembunyikan (diganti crosshair custom) & mouse dikunci
        # supaya tidak kabur keluar window saat lagi main
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)

    def _screen_to_game_pos(self, pos):
        x = (pos[0] - self.render_offset[0]) / self.render_scale
        y = (pos[1] - self.render_offset[1]) / self.render_scale
        return x, y

    # ---- setup ----
    def reset(self):
        global game_map_is_wall_cache
        self.map = GameMap()
        game_map_is_wall_cache = self.map
        px, py = self.map.random_floor_pos()
        self.player = Player((px, py))
        self.bullets = []
        self.ghosts = []
        self.chests = []
        self.poison_bolts = []
        self.kills = 0
        self.score = 0
        self.ghost_spawn_timer = 0
        self.chest_spawn_timer = 0
        self.gacha_banner = None
        self.gacha_spin = None
        self.state = "PLAYING"
        for _ in range(5):
            self._spawn_ghost()

    # ---- spawning (kesulitan naik seiring jumlah hantu terbunuh) ----
    # spawn jauh lebih cepat & padat daripada versi awal
    def max_alive_ghosts(self):
        return min(6 + self.kills // 2, 30)

    def ghost_spawn_interval(self):
        return max(600 - self.kills * 25, 120)

    def _pick_ghost_type(self):
        # hantu normal makin jarang, tipe spesial (cepat/dash/racun) makin
        # sering muncul seiring banyaknya hantu yang sudah dibunuh
        bonus = min(self.kills, 40)
        weights = [
            max(50 - bonus, 15),     # Ghost (normal)
            20 + bonus // 3,          # FastGhost
            18 + bonus // 3,          # DasherGhost
            14 + bonus // 4,          # PoisonGhost
        ]
        return random.choices(GHOST_TYPES, weights=weights, k=1)[0]

    def _spawn_ghost(self):
        pos = self.map.random_floor_pos(
            exclude_center=(self.player.pos.x, self.player.pos.y), min_dist=260
        )
        ghost_cls = self._pick_ghost_type()
        base_hp = 30 + self.kills * 2
        base_speed = min(1.3 + self.kills * 0.03, 3.0)
        hp = base_hp * ghost_cls.hp_mult
        speed = base_speed * ghost_cls.speed_mult
        self.ghosts.append(ghost_cls(pos, hp, speed))

    def _maybe_spawn_chest(self):
        if len(self.chests) >= 3:
            return
        pos = self.map.random_floor_pos()
        self.chests.append(WeaponChest(pos))

    def _gacha_roll(self):
        # gacha ala CS: tiap senjata punya drop_weight/rarity sendiri
        # (lihat rarity di class Pistol/Rifle/MachineGun/Shotgun)
        weights = [w.drop_weight for w in WEAPON_TYPES]
        return random.choices(WEAPON_TYPES, weights=weights, k=1)[0]

    def _start_gacha(self):
        # bikin "reel" -- deretan senjata acak buat efek muter, dengan hasil
        # asli (won_cls) disisipkan di index tertentu supaya reel berhenti
        # tepat di situ saat animasi selesai (persis case-opening CS)
        won_cls = self._gacha_roll()
        win_index = 26
        reel = [random.choice(WEAPON_TYPES) for _ in range(win_index + 6)]
        reel[win_index] = won_cls
        self.gacha_spin = {
            "reel": reel,
            "win_index": win_index,
            "won_cls": won_cls,
            "elapsed": 0,
            "duration": 3200,
            "item_w": 74,
        }

    # ---- update ----
    def update(self, dt):
        if self.state != "PLAYING":
            return
        now = pygame.time.get_ticks()
        keys = pygame.key.get_pressed()
        self.player.handle_input(keys, self.map)
        self.player.aim(self._screen_to_game_pos(pygame.mouse.get_pos()))
        self.player.update(dt, self.map)

        if pygame.mouse.get_pressed()[0]:
            self.bullets.extend(self.player.try_shoot(now))

        for b in self.bullets:
            b.update()
        self.bullets = [b for b in self.bullets if b.alive]

        for g in self.ghosts:
            spawned = g.update(dt, self.player, self.map)
            if spawned:
                self.poison_bolts.extend(spawned)

        for pb in self.poison_bolts:
            pb.update(self.map)
        self.poison_bolts = [pb for pb in self.poison_bolts if pb.alive]

        # peluru vs hantu
        for b in self.bullets:
            if not b.alive:
                continue
            for g in self.ghosts:
                if g.alive and b.get_rect().colliderect(g.get_rect()):
                    g.take_damage(b.damage)
                    b.alive = False
                    if not g.alive:
                        self.kills += 1
                        self.score += 10
                    break
        self.bullets = [b for b in self.bullets if b.alive]
        self.ghosts = [g for g in self.ghosts if g.alive]

        # hantu vs player (kontak = damage, tidak saling menghalangi gerak)
        for g in self.ghosts:
            if g.contact_cd <= 0 and g.get_rect().colliderect(self.player.get_rect()):
                self.player.take_damage(g.contact_damage)
                g.contact_cd = 700

        # semburan racun vs player
        for pb in self.poison_bolts:
            if pb.alive and pb.get_rect().colliderect(self.player.get_rect()):
                self.player.take_damage(pb.damage)
                self.player.apply_poison(pb.poison_duration, pb.poison_dps)
                pb.alive = False
        self.poison_bolts = [pb for pb in self.poison_bolts if pb.alive]

        # buka peti = mulai animasi spin gacha (cuma boleh 1 spin jalan sekaligus)
        for chest in self.chests[:]:
            chest.update(dt)
            if self.gacha_spin is None and chest.get_rect().colliderect(self.player.get_rect()):
                self._start_gacha()
                self.chests.remove(chest)

        if self.gacha_spin:
            self.gacha_spin["elapsed"] += dt
            if self.gacha_spin["elapsed"] >= self.gacha_spin["duration"]:
                won_cls = self.gacha_spin["won_cls"]
                self.player.weapon = won_cls()
                self.gacha_banner = {
                    "text": f"Dapat: {won_cls.name}  [{won_cls.rarity}]",
                    "color": won_cls.rarity_color,
                    "icon": self.weapon_icons.get(won_cls.__name__),
                    "timer": 1600,
                }
                self.gacha_spin = None

        if self.gacha_banner:
            self.gacha_banner["timer"] -= dt
            if self.gacha_banner["timer"] <= 0:
                self.gacha_banner = None

        # timer spawn
        self.ghost_spawn_timer += dt
        if self.ghost_spawn_timer >= self.ghost_spawn_interval() and len(self.ghosts) < self.max_alive_ghosts():
            self.ghost_spawn_timer = 0
            self._spawn_ghost()

        self.chest_spawn_timer += dt
        if self.chest_spawn_timer >= 4000:
            self.chest_spawn_timer = 0
            self._maybe_spawn_chest()

        if self.player.hp <= 0:
            self.state = "GAMEOVER"

    # ---- drawing ----
    def draw_world(self):
        world = pygame.Surface((MAP_W, MAP_H))
        world.fill(BLACK)
        self.map.draw(world)
        for chest in self.chests:
            chest.draw(world)
        for g in self.ghosts:
            g.draw(world, sprite=self.ghost_sprites.get(type(g).__name__))
        for pb in self.poison_bolts:
            pb.draw(world)
        for b in self.bullets:
            b.draw(world)
        self.player.draw(world, sprite=self.player_sprite)
        return world

    def apply_fog(self, world):
        fog = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        fog.fill((0, 0, 0, 235))
        mask_rect = self.light_mask.get_rect(center=(int(self.player.pos.x), int(self.player.pos.y)))
        fog.blit(self.light_mask, mask_rect, special_flags=pygame.BLEND_RGBA_SUB)
        world.blit(fog, (0, 0))
        return world

    def draw_player_status(self, surf):
        # HP + amunisi ditempel tepat di bawah player, ikut posisinya di map
        p = self.player
        bar_w, bar_h = 52, 7
        cx = p.pos.x
        top = p.pos.y + p.radius + 9

        pygame.draw.rect(surf, (50, 10, 10), (cx - bar_w / 2, top, bar_w, bar_h))
        ratio = max(0, p.hp / p.max_hp)
        pygame.draw.rect(surf, GREEN if ratio > 0.3 else RED, (cx - bar_w / 2, top, bar_w * ratio, bar_h))
        pygame.draw.rect(surf, WHITE, (cx - bar_w / 2, top, bar_w, bar_h), 1)

        stamina_top = top + bar_h + 3
        stamina_ratio = max(0, min(1, p.stamina / p.max_stamina))
        pygame.draw.rect(surf, (25, 45, 55),
                         (cx - bar_w / 2, stamina_top, bar_w, bar_h))
        pygame.draw.rect(surf, (70, 210, 255),
                         (cx - bar_w / 2, stamina_top, bar_w * stamina_ratio, bar_h))
        pygame.draw.rect(surf, WHITE,
                         (cx - bar_w / 2, stamina_top, bar_w, bar_h), 1)

        weapon = p.weapon
        empty = weapon.ammo <= 0
        blink_on = (pygame.time.get_ticks() // 200) % 2 == 0
        ammo_color = (RED if blink_on else (130, 25, 25)) if empty else YELLOW
        label_text = "KOSONG!" if empty else f"{weapon.name} {weapon.ammo}/{weapon.max_ammo}"
        label = self.font_small.render(label_text, True, ammo_color)
        label_rect = label.get_rect(midtop=(cx, stamina_top + bar_h + 4))

        # latar tipis translucent biar teks kebaca di atas rumput/pohon
        bg = pygame.Surface((label_rect.width + 10, label_rect.height + 4), pygame.SRCALPHA)
        bg.fill((10, 10, 14, 140))
        surf.blit(bg, (label_rect.x - 5, label_rect.y - 2))
        surf.blit(label, label_rect)

        if p.poison_time > 0:
            pt = self.font_small.render("☠ Teracun", True, (140, 220, 110))
            pt_rect = pt.get_rect(midtop=(cx, label_rect.bottom + 2))
            bg2 = pygame.Surface((pt_rect.width + 10, pt_rect.height + 4), pygame.SRCALPHA)
            bg2.fill((10, 10, 14, 140))
            surf.blit(bg2, (pt_rect.x - 5, pt_rect.y - 2))
            surf.blit(pt, pt_rect)

    def draw_top_right_stats(self, surf):
        margin = 16
        score_txt = self.font.render(f"Skor: {self.score}", True, WHITE)
        kills_txt = self.font_small.render(f"Hantu dibunuh: {self.kills}", True, (200, 200, 210))
        w = max(score_txt.get_width(), kills_txt.get_width()) + 20
        h = score_txt.get_height() + kills_txt.get_height() + 14
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (10, 10, 14, 150), (0, 0, w, h), border_radius=8)
        panel.blit(score_txt, (10, 6))
        panel.blit(kills_txt, (10, 8 + score_txt.get_height()))
        surf.blit(panel, (SCREEN_W - w - margin, margin))

    def draw_gacha_spin(self, surf):
        spin = self.gacha_spin
        if not spin:
            return
        item_w = spin["item_w"]

        panel_w, panel_h = 420, 96
        rect = pygame.Rect(0, 0, panel_w, panel_h)
        rect.center = (SCREEN_W // 2, 92)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (15, 14, 20, 235), (0, 0, panel_w, panel_h), border_radius=10)
        pygame.draw.rect(panel, (95, 95, 105, 255), (0, 0, panel_w, panel_h), 2, border_radius=10)

        strip_area = pygame.Rect(10, 10, panel_w - 20, panel_h - 34)
        marker_x = strip_area.centerx

        t = min(1.0, spin["elapsed"] / spin["duration"])
        eased = 1 - (1 - t) ** 3   # ease-out kubik: cepat di awal, melambat di akhir
        # target scroll dihitung supaya slot win_index PERSIS di bawah marker
        # (sebelumnya lupa dikurangi offset marker dari tepi kiri strip -> reel
        # berhenti di slot yang salah, beda dari senjata yang benar-benar didapat)
        final_scroll = (spin["win_index"] * item_w + item_w / 2) - (marker_x - strip_area.left)
        scroll = final_scroll * eased

        prev_clip = panel.get_clip()
        panel.set_clip(strip_area)
        for i, cls in enumerate(spin["reel"]):
            slot_cx = strip_area.left + (i * item_w + item_w / 2) - scroll
            if slot_cx < strip_area.left - item_w / 2 or slot_cx > strip_area.right + item_w / 2:
                continue
            box = pygame.Rect(0, 0, item_w - 10, strip_area.height - 6)
            box.center = (int(slot_cx), strip_area.centery)
            pygame.draw.rect(panel, (30, 28, 38), box, border_radius=6)
            pygame.draw.rect(panel, cls.rarity_color, box, 2, border_radius=6)
            icon = self.weapon_icons.get(cls.__name__)
            if icon:
                panel.blit(icon, icon.get_rect(center=box.center))
            else:
                label = self.font_small.render(cls.name[:3].upper(), True, cls.rarity_color)
                panel.blit(label, label.get_rect(center=box.center))
        panel.set_clip(prev_clip)

        # penanda posisi hasil akhir
        pygame.draw.polygon(panel, WHITE, [(marker_x - 7, 2), (marker_x + 7, 2), (marker_x, 13)])
        pygame.draw.line(panel, (255, 255, 255, 110), (marker_x, strip_area.top), (marker_x, strip_area.bottom), 1)

        caption = self.font_small.render("Membuka peti...", True, (200, 200, 210))
        panel.blit(caption, caption.get_rect(center=(panel_w // 2, panel_h - 12)))

        surf.blit(panel, rect)

    def draw_gacha_banner(self, surf):
        if not self.gacha_banner:
            return
        banner = self.gacha_banner
        t = banner["timer"]
        alpha = 255 if t > 400 else int(255 * (t / 400))
        w, h = 340, 62
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (SCREEN_W // 2, 90)
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (15, 14, 20, min(230, alpha)), (0, 0, w, h), border_radius=10)
        pygame.draw.rect(panel, banner["color"] + (alpha,), (0, 0, w, h), 3, border_radius=10)
        content_x = 16
        if banner["icon"]:
            icon = banner["icon"].copy()
            icon.set_alpha(alpha)
            panel.blit(icon, (content_x, h // 2 - icon.get_height() // 2))
            content_x += banner["icon"].get_width() + 12
        label = self.font.render(banner["text"], True, banner["color"])
        label.set_alpha(alpha)
        panel.blit(label, (content_x, h // 2 - label.get_height() // 2))
        surf.blit(panel, rect)

    def draw_hit_flash(self, surf):
        if self.player.hit_flash > 0:
            alpha = int(140 * (self.player.hit_flash / 260))
            flash = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            flash.fill((200, 0, 0, alpha))
            surf.blit(flash, (0, 0))

    def draw_menu(self):
        self.game_surface.fill(BLACK)
        title = self.font_big.render("GUNT", True, RED)
        self.game_surface.blit(title, title.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 - 90)))
        lines = [
            "WASD - bergerak    |    Klik kiri - tembak ke arah kursor",
            "Senjata punya amunisi terbatas -- buka PETI untuk gacha senjata baru",
            "Putih normal | Oranye cepat | Ungu dash | Hijau nyemburin racun",
            "F11 - ganti mode layar (fullscreen/jendela)",
            "Tidak ada batas waktu -- bertahanlah selama mungkin",
            "",
            "Tekan SPACE untuk mulai",
        ]
        for i, line in enumerate(lines):
            txt = self.font.render(line, True, WHITE)
            self.game_surface.blit(txt, txt.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 - 20 + i * 30)))

    def draw_gameover(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.game_surface.blit(overlay, (0, 0))
        title = self.font_big.render("MATI", True, RED)
        self.game_surface.blit(title, title.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 - 50)))
        sc = self.font.render(f"Skor akhir: {self.score}   |   Hantu dibunuh: {self.kills}", True, WHITE)
        self.game_surface.blit(sc, sc.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2)))
        hint = self.font_small.render("Tekan R untuk main lagi, ESC untuk keluar", True, (200, 200, 200))
        self.game_surface.blit(hint, hint.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 + 36)))

    def draw(self):
        if self.state == "MENU":
            self.draw_menu()
        else:
            world = self.draw_world()
            world = self.apply_fog(world)
            self.game_surface.blit(world, (0, 0))
            self.draw_hit_flash(self.game_surface)
            self.draw_player_status(self.game_surface)
            if self.gacha_spin:
                self.draw_gacha_spin(self.game_surface)
            self.draw_gacha_banner(self.game_surface)
            self.draw_top_right_stats(self.game_surface)
            if self.state == "GAMEOVER":
                self.draw_gameover()
        self._present()

    def _present(self):
        # scale game_surface (resolusi logis tetap) ke ukuran jendela/layar
        # sungguhan saat ini, dijaga tetap proporsional (letterbox), lalu tampilkan
        sw, sh = self.screen.get_size()
        scale = min(sw / SCREEN_W, sh / SCREEN_H)
        new_w, new_h = max(1, int(SCREEN_W * scale)), max(1, int(SCREEN_H * scale))
        offset = ((sw - new_w) // 2, (sh - new_h) // 2)
        self.render_scale = scale
        self.render_offset = offset
        self.screen.fill(BLACK)
        scaled = pygame.transform.smoothscale(self.game_surface, (new_w, new_h))
        self.screen.blit(scaled, offset)
        # crosshair digambar terakhir, langsung di resolusi layar asli (bukan
        # lewat game_surface yang di-scale) supaya selalu tajam & pas di kursor
        self.draw_crosshair(pygame.mouse.get_pos())
        pygame.display.flip()

    def draw_crosshair(self, pos):
        x, y = int(pos[0]), int(pos[1])
        size, gap = 9, 5
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            start = (x + dx * gap, y + dy * gap)
            end = (x + dx * (gap + size), y + dy * (gap + size))
            pygame.draw.line(self.screen, (0, 0, 0), start, end, 4)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            start = (x + dx * gap, y + dy * gap)
            end = (x + dx * (gap + size), y + dy * (gap + size))
            pygame.draw.line(self.screen, WHITE, start, end, 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (x, y), 2)
        pygame.draw.circle(self.screen, WHITE, (x, y), 1)

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.VIDEORESIZE:
                    self.resize_window(event.size)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.fullscreen:
                            self.toggle_fullscreen()   # ESC keluar dari fullscreen dulu
                        else:
                            pygame.quit()
                            sys.exit()
                    elif event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    elif self.state == "PLAYING" and event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        self.player.try_dash(self.map)
                    elif self.state == "MENU" and event.key == pygame.K_SPACE:
                        self.reset()
                    elif self.state == "GAMEOVER" and event.key == pygame.K_r:
                        self.reset()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    pygame.init()
    Game().run()
