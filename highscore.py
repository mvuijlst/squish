import os
import sys
import pygame
import datetime
from pygame.locals import *
import config
import utils
import drawing # Now this module exists

class HighScoreManager:
    def __init__(self):
        self.scores = []
        self.load()

    def load(self):
        """Loads high scores from the encrypted file."""
        if not os.path.exists(utils.resource_path(config.SCORE_FILE)):
            self.scores = []
            self.save() # Create an empty file if it doesn't exist
            return

        try:
            with open(utils.resource_path(config.SCORE_FILE), "rb") as f:
                encrypted = f.read()

            # Handle empty file case
            if not encrypted:
                self.scores = []
                return

            decrypted = utils.decrypt_xor(encrypted, config.XOR_KEY).decode("utf-8", errors="ignore")
            lines = decrypted.strip().split("\n")
            loaded_scores = []
            for line in lines:
                parts = line.split("|")
                if len(parts) == 5:
                    dt_str, lvl_str, scr_str, time_str, name_str = parts
                    try:
                        record = {
                            "date": dt_str,
                            "level": lvl_str,
                            "score": int(scr_str),
                            "time": int(time_str),
                            "name": name_str,
                            "highlight": False
                        }
                        if record["name"].endswith("##"):
                            record["name"] = record["name"][:-2]
                            record["highlight"] = True
                        loaded_scores.append(record)
                    except ValueError:
                        print(f"WARN: Skipping invalid score line: {line}")
                        continue # Skip malformed lines
            # Sort after loading all valid entries
            self.scores = sorted(loaded_scores, key=lambda s: (-s["score"], s["time"]))

        except FileNotFoundError:
            self.scores = []
        except Exception as e:
            print(f"ERROR loading high scores: {e}. Resetting scores.")
            self.scores = []
            # Optionally backup the corrupted file here
            self.save() # Save an empty list to reset

    def save(self):
        """Saves the current high scores to the encrypted file."""
        # Ensure scores are sorted and capped before saving
        self.scores = sorted(self.scores, key=lambda s: (-s["score"], s["time"]))[:config.MAX_HIGH_SCORES]
        lines = []
        for s in self.scores:
            nm = s["name"] + ("##" if s.get("highlight") else "")
            # Ensure all parts are strings before joining
            line = "|".join(map(str, [s["date"], s["level"], s["score"], s["time"], nm]))
            lines.append(line)

        data = "\n".join(lines)
        encrypted = utils.encrypt_xor(data.encode("utf-8"), config.XOR_KEY)

        try:
            with open(utils.resource_path(config.SCORE_FILE), "wb") as f:
                f.write(encrypted)
        except Exception as e:
            print(f"ERROR saving high scores: {e}")

    def _ask_player_name(self, screen, clock) -> str:
        """Internal helper to get player name via keyboard input."""
        name = ""
        input_active = True
        prompt_y = 100
        name_y = 140
        max_name_len = 30 # Limit name length

        while input_active:
            for evt in pygame.event.get():
                if evt.type == QUIT:
                    pygame.quit(); sys.exit()
                elif evt.type == KEYDOWN:
                    if evt.key == K_RETURN:
                        input_active = False
                    elif evt.key == K_BACKSPACE:
                        name = name[:-1]
                    elif evt.key == K_ESCAPE:
                        name = "anonymous" # Allow escaping
                        input_active = False
                    else:
                        # Append printable characters, respecting length limit
                        if len(name) < max_name_len and evt.unicode.isprintable():
                            name += evt.unicode

            screen.fill((0, 0, 0))
            drawing.draw_text(screen, "High score! Enter your name:", 50, prompt_y, config.TEXT_COLOR_DEFAULT)
            # Display name with a blinking cursor simulation (optional)
            display_name = name + ("_" if pygame.time.get_ticks() // 500 % 2 == 0 else " ")
            drawing.draw_text(screen, display_name, 50, name_y, config.HIGHLIGHT_COLOR)
            pygame.display.flip()
            clock.tick(15) # Keep responsiveness without high CPU

        return name.strip() or "anonymous" # Ensure non-empty name

    def _check_qualification(self, total_score: int, level: str, time_played: int) -> bool:
        """Checks if a score qualifies for the high score list."""
        # Reset highlights before checking
        for s in self.scores:
            s["highlight"] = False

        # Check overall qualification (top N)
        if len(self.scores) < config.MAX_HIGH_SCORES:
            return True
        worst_overall = self.scores[-1] # Scores are sorted descending
        if total_score > worst_overall['score'] or \
           (total_score == worst_overall['score'] and time_played < worst_overall['time']):
            return True

        # Check per-level qualification (top M for that level letter)
        level_key = level[0] if level else ""
        if not level_key: return False # Cannot qualify if level is invalid

        level_scores = [s for s in self.scores if s["level"] and s["level"].startswith(level_key)]
        # Sort just this subset
        level_scores = sorted(level_scores, key=lambda s: (-s["score"], s["time"]))

        if len(level_scores) < config.MAX_LEVEL_HIGH_SCORES:
             return True
        worst_level = level_scores[config.MAX_LEVEL_HIGH_SCORES - 1]
        if total_score > worst_level["score"] or \
           (total_score == worst_level["score"] and time_played < worst_level["time"]):
            return True

        return False

    def maybe_record_and_show(self, total_score: int, level: str, screen, clock, time_played: int):
        """Checks if score qualifies, asks for name if so, adds score, saves, and shows the list."""
        qualifies = self._check_qualification(total_score, level, time_played)

        if qualifies:
            name = self._ask_player_name(screen, clock)
            highlight_new = True
            if name == "anonymous": # Don't highlight if escaped or entered nothing
                highlight_new = False
        else:
            name = "anonymous" # Not used, but for clarity
            highlight_new = False

        # Add the new record if qualified
        if qualifies:
            dt_str = datetime.datetime.now().isoformat(timespec="seconds")
            new_record = {
                "date": dt_str,
                "level": level,
                "score": total_score,
                "time": time_played,
                "name": name,
                "highlight": highlight_new # Mark the new entry
            }
            self.scores.append(new_record)
            self.save() # Save the updated list

        # Always show the high score screen after a game ends
        self.show_screen(screen, clock)


    def _show_overall_scroll(self, surface, clock):
        """Displays the overall high scores with scrolling."""
        line_spacing = 32
        x_margin = 10
        y_start = 10

        lines = []
        lines.append(("header", "    Name                     Date      Score  Time   Rank"))
        # Use the current, sorted scores
        for idx, s in enumerate(self.scores, 1):
            color = config.HIGHLIGHT_COLOR if s.get("highlight") else config.TEXT_COLOR_DEFAULT
            name_full = s["name"]
            if len(name_full) > 21: # Adjusted max length for layout
                name_full = name_full[:18] + "..."
            date_display = s["date"][:10] # Just YYYY-MM-DD

            # Determine rank display (Level + Rank char if not digit ending)
            lvl = s["level"]
            rank_char = "\x13" # Example rank character
            if lvl and lvl[-1].isdigit():
                rank_display = lvl
            else:
                rank_display = (lvl or "?") + rank_char # Handle potentially empty level

            # Format line with padding
            line_text = f"{idx:2d}. {name_full}"
            filler_len = max(0, 28 - len(line_text)) # Adjust length based on name
            filler = "." * filler_len
            remainder = f" {date_display:<10}  {s['score']:>5d}  {utils.format_time(s['time']):>5}  {rank_display:>3}" # Adjusted widths
            full_line = line_text + filler + remainder
            lines.append(("line", full_line, color))

        lines.append(("footer", "Press TAB=Level View | UP/DOWN=Scroll | ESC=Exit"))

        total_content_height = len(lines) * line_spacing
        view_height = surface.get_height() - y_start - 40 # Account for header/footer space
        max_scroll = max(0, total_content_height - view_height)
        scroll_offset = 0
        line_height = config.CHAR_HEIGHT * config.SCALE_Y + 10 # Approximate line height for drawing

        active = True
        while active:
            surface.fill((0, 0, 0))
            y = y_start

            # Draw Header
            if lines and lines[0][0] == "header":
                 drawing.draw_text(surface, lines[0][1], x_margin, y, config.TEXT_COLOR_DEFAULT)
                 y += line_spacing

            # Draw visible score lines
            first_visible_line = int(scroll_offset / line_spacing)
            last_visible_line = first_visible_line + int(view_height / line_spacing) + 2 # Draw a bit extra

            current_y = y_start + line_spacing - (scroll_offset % line_spacing) # Start drawing adjusted by scroll

            for i in range(first_visible_line, min(last_visible_line, len(lines) -1)): # Exclude footer for now
                 entry = lines[i+1] # +1 because header is lines[0]
                 etype = entry[0]
                 if etype == "line":
                     text, color = entry[1], entry[2]
                     drawing.draw_text(surface, text, x_margin, current_y, color)
                     current_y += line_spacing


            # Draw Footer at the bottom
            if lines and lines[-1][0] == "footer":
                drawing.draw_text(surface, lines[-1][1], x_margin, surface.get_height() - 30, config.TEXT_COLOR_DEFAULT)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        return "exit"
                    elif event.key == K_TAB:
                        return "tab"
                    elif event.key == K_UP:
                        scroll_offset = max(0, scroll_offset - line_spacing)
                    elif event.key == K_DOWN:
                        scroll_offset = min(max_scroll, scroll_offset + line_spacing)
                elif event.type == MOUSEWHEEL: # Add mouse wheel scrolling
                    if event.y > 0: # Scroll up
                         scroll_offset = max(0, scroll_offset - line_spacing * 2)
                    elif event.y < 0: # Scroll down
                         scroll_offset = min(max_scroll, scroll_offset + line_spacing * 2)

            clock.tick(30) # Increase tick rate for smoother scrolling


    def _show_by_level_scroll(self, surface, clock):
        """Displays the top scores per level with scrolling."""
        line_spacing = 32
        x_margin = 10
        y_start = 10

        lines = []
        groups = {}
        # Group scores by the first letter of the level
        for s in self.scores:
            lvl_letter = s["level"][0] if s["level"] else "?" # Group unknowns under '?'
            groups.setdefault(lvl_letter, []).append(s)

        # Sort groups by level letter and format lines
        for lvl_letter in sorted(groups.keys()):
            lines.append(("group", f"--- Level {lvl_letter} ---", config.HIGHLIGHT_COLOR))
            # Sort scores within the group and take top N
            group_scores = sorted(groups[lvl_letter], key=lambda x: (-x["score"], x["time"]))[:config.MAX_LEVEL_HIGH_SCORES]

            for idx, rec in enumerate(group_scores, 1):
                color = config.HIGHLIGHT_COLOR if rec.get("highlight") else config.TEXT_COLOR_DEFAULT
                name_full = rec["name"]
                if len(name_full) > 21: name_full = name_full[:18] + "..."
                date_display = rec["date"][:10]

                # Rank display logic (same as overall view)
                lvl = rec["level"]
                rank_char = "\x13"
                if lvl and lvl[-1].isdigit(): rank_display = lvl
                else: rank_display = (lvl or "?") + rank_char

                # Format line
                line_text = f"{idx}. {name_full}"
                filler_len = max(0, 28 - len(line_text))
                filler = "." * filler_len
                remainder = f" {date_display:<10}  {rec['score']:>5d}  {utils.format_time(rec['time']):>5}  {rank_display:>3}"
                full_line = line_text + filler + remainder
                lines.append(("line", full_line, color))
            lines.append(("blank",)) # Add space between groups

        lines.append(("footer", "Press TAB=Overall View | UP/DOWN=Scroll | ESC=Exit"))

        # Calculate scrolling parameters
        total_content_height = 0
        for entry in lines:
             total_content_height += line_spacing # Each entry takes up space

        view_height = surface.get_height() - y_start - 40
        max_scroll = max(0, total_content_height - view_height)
        scroll_offset = 0
        line_height = config.CHAR_HEIGHT * config.SCALE_Y + 10

        active = True
        while active:
            surface.fill((0, 0, 0))

            # Calculate visible lines based on scroll offset
            first_visible_idx = int(scroll_offset / line_spacing)
            last_visible_idx = first_visible_idx + int(view_height / line_spacing) + 2

            current_y = y_start - (scroll_offset % line_spacing) # Start drawing adjusted by scroll

            # Draw visible lines
            for i in range(first_visible_idx, min(last_visible_idx, len(lines) -1)): # Exclude footer
                entry = lines[i]
                etype = entry[0]
                if etype in ("group", "line"):
                    text, color = entry[1], entry[2]
                    drawing.draw_text(surface, text, x_margin, current_y, color)
                    current_y += line_spacing
                elif etype == "blank":
                    current_y += line_spacing # Just advance position

            # Draw Footer
            if lines and lines[-1][0] == "footer":
                 drawing.draw_text(surface, lines[-1][1], x_margin, surface.get_height() - 30, config.TEXT_COLOR_DEFAULT)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        return "exit"
                    elif event.key == K_TAB:
                        return "tab"
                    elif event.key == K_UP:
                        scroll_offset = max(0, scroll_offset - line_spacing)
                    elif event.key == K_DOWN:
                        scroll_offset = min(max_scroll, scroll_offset + line_spacing)
                elif event.type == MOUSEWHEEL:
                    if event.y > 0: scroll_offset = max(0, scroll_offset - line_spacing * 2)
                    elif event.y < 0: scroll_offset = min(max_scroll, scroll_offset + line_spacing * 2)

            clock.tick(30)


    def show_screen(self, surface, clock):
        """Shows the high score screen, allowing toggling between views."""
        view_mode = 0  # 0 for overall, 1 for per-level
        while True:
            if view_mode == 0:
                result = self._show_overall_scroll(surface, clock)
            else:
                result = self._show_by_level_scroll(surface, clock)

            if result == "tab":
                view_mode = 1 - view_mode # Toggle view
            elif result == "exit":
                return # Exit the high score screen
            # Add handling for other potential results if needed
