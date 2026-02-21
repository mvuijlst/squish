# S Q U I S H — v5.0

> A real-time, keyboard-driven arcade puzzle game inspired by the classic **Beast** (WordPerfect Office, 1984).

---

## Overview

You are a lone character on a 40 × 25 grid packed with moveable blocks and relentless enemies.  
**Your only weapon is physics** — trap enemies by pushing blocks into them.  
Survive every enemy on the board to clear the sublevel, then repeat until the main level is complete.

The game is deliberately retro: rendered entirely from a DOS codepage-437 sprite sheet, driven entirely by the keyboard, with a real-time clock ticking away as the enemies grow faster between sublevels.

---

## Enemy Types

| Symbol | Name | Behaviour |
|--------|------|-----------|
| `├┤` | **Hunter** | Pursues you with A★ pathfinding and diagonal movement. Accuracy and speed are configurable per level. |
| `ΦΦ` | **Pusher** | Moves orthogonally and pushes block chains toward you. Can be used against itself. |
| `╟╢` | **Sentinel** | Behaves like a Hunter but uses separate speed/accuracy settings — often harder in later levels. |
| `○○` | **Egg** | Stationary but ticking — hatches into a Pusher after a configurable incubation period. Colour shifts from yellow → orange → flashing red as hatching nears. |

Squish an enemy by pushing a block into it while it has a wall, block, or another enemy directly behind it.

---

## Power-ups (New in v5)

Power-ups appear as glowing characters scattered across each sublevel.  
Walk into one to activate it instantly.

| Symbol | Colour | Effect |
|--------|--------|--------|
| `☼☼` | Cyan | **Slow** — halves enemy move frequency for 8 seconds |
| `☺☺` | Green | **Shield** — absorbs the next lethal enemy hit |
| `♥♥` | Yellow | **Extra Life** — grants +1 life (capped at 5) |

---

## Controls

| Key | Action |
|-----|--------|
| Arrow keys | Move / push blocks |
| Shift + Arrow | **Pull** a block behind you while stepping forward (on levels with pull-blocks enabled) |
| Esc | Pause game |
| Q | Quit to level select (with confirmation) |
| H (level select) | View high scores |
| A (level select) | Toggle art style (DOS / ST sprite sheet) |

---

## Scoring

| Action | Points |
|--------|--------|
| Squish a Hunter | 2 |
| Squish an Egg | 3 |
| Squish a Pusher | 5 |
| Squish a Sentinel | 7 |
| Collect a power-up | 1 |
| Complete a sublevel | 5 + difficulty bonus |
| **Perfect sublevel** (no lives lost) | +10 + (sublevel index × 5) |
| **Combo** (kills within 3 s of each other) | base × combo multiplier (up to ×5) |

---

## Level Progression

Each main level (A, B, C…) consists of one or more **sublevels**.  
Enemy counts increase with each sublevel, and — when `speed_up` is enabled for that level — enemies also move progressively faster (capped at a minimum interval so the game stays fair).  
Complete all sublevels of a main level to post a high score and move on.

---

## Running the Game

```bash
git clone https://github.com/mvuijlst/squish.git
cd squish
pip install -r requirements.txt
python squish.py
```

> **Note for Python 3.14+:** the standard `pygame` package does not yet ship binary wheels for 3.14.
> Install `pygame-ce` instead (fully API-compatible community fork):
> `pip install pygame-ce`

A pre-built `squish.exe` is available in the [Releases](../../releases) section for Windows users who prefer not to install Python.

---

## Release Notes

### v5.0 (2026-02-21)

#### New features

- **Power-up system** — three collectible items (Slow, Shield, Extra Life) spawn on every sublevel.
- **Block-pull mechanic** — on levels with `pull_blocks: true`, hold **Shift** while pressing an arrow key to drag the moveable block behind you as you step forward.  This flag was defined in the level JSON since v4 but was never implemented; it is fully wired up in v5.
- **Combo multiplier** — killing enemies within a 3-second window chains into a ×2 … ×5 multiplier shown on screen until the window expires.
- **Speed-up per sublevel** — levels with `speed_up: true` now actually accelerate between sublevels (enemy `speed_ms` × 0.90 per round, floored at 150 ms).  Previously the flag was loaded but had no effect.
- **Particle effects** — squishing an enemy triggers a burst of coloured particles at the kill location.
- **Screen-flash feedback** — a red overlay flashes briefly on a lethal hit; a blue-tinted flash indicates a shield absorbing the hit.
- **Wave banner** — a "ROUND N" banner fades in/out at the start of each sublevel.
- **Doubled status bar** — a second status row shows active power-up countdowns and a quick-reference keyboard hint.
- **Lives cap** — maximum lives capped at 5 (configurable via `config.MAX_LIVES`).
- **Perfect-sublevel bonus** — completing a sublevel without losing a life awards extra points.

#### Fixes / improvements

- `pull_blocks` level flag is now honoured at runtime (was a no-op in v4).
- `speed_up` level flag is now honoured at runtime (was a no-op in v4).
- Enemy kill scoring now routes through `add_kill_score()` which applies the combo multiplier, replacing direct `add_score()` calls.
- Level-details screen now shows the pull-block setting and the Shift+arrow hint.
- Pushing a block over a power-up cell silently destroys the power-up (blocks win).

---

### v4.0.1 (2025)

- First public release after complete rewrite from v1.2.0.
- Modular source split into `squish.py`, `config.py`, `utils.py`, `drawing.py`, `resources.py`, `highscore.py`.
- `GameState` class replacing scattered global variables.
- A★ pathfinding for Hunters and Sentinels (with diagonal movement).
- Per-level and global high score tables, XOR-encrypted on disk.
- Dual sprite-sheet support (DOS and Atari ST; toggle with **A** at level select).
- Spawn animation and best-spot algorithm for player re-entry after death.
- Sublevel completion bonuses and progression-based enemy scaling.

---

## Contributing

Bug reports and pull requests are welcome via GitHub Issues and PRs.

## License

MIT — see `LICENSE`.
