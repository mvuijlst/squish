import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import os
from typing import List, Dict

SCORE_FILE = "highscores.dat"

# Define styles for table contents only
TABLE_BG_COLOR = "black"
TABLE_FG_COLOR = "white"
TABLE_FONT = ("Courier", 10)  # Monospace font for table contents

def encrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return bytes(b ^ key for b in data)

def load_highscores() -> List[Dict]:
    if not os.path.exists(SCORE_FILE):
        return []
    
    with open(SCORE_FILE, "rb") as f:
        encrypted = f.read()
    
    data = encrypt_xor(encrypted, 0xAA).decode("utf-8")
    scores = []
    
    for line in data.split("\n"):
        if not line:
            continue
        date, level, score, time, name = line.split("|")
        scores.append({
            "date": date,
            "level": level,
            "score": int(score),
            "time": int(time),
            "name": name
        })
    
    return sorted(scores, key=lambda s: (-s["score"], s["time"]))

def save_highscores(scores: List[Dict]):
    scores = sorted(scores, key=lambda s: (-s["score"], s["time"]))[:20]
    lines = []
    for s in scores:
        lines.append(f'{s["date"]}|{s["level"]}|{s["score"]}|{s["time"]}|{s["name"]}')
    data = "\n".join(lines)
    encrypted = encrypt_xor(data.encode("utf-8"), 0xAA)
    with open(SCORE_FILE, "wb") as f:
        f.write(encrypted)

class EditableTreeview(ttk.Treeview):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind('<Double-1>', self.on_double_click)
        
    def on_double_click(self, event):
        item = self.identify_row(event.y)
        column = self.identify_column(event.x)
        
        if not item or not column:
            return
            
        column_name = self["columns"][int(column[1]) - 1]
        current_value = self.item(item)["values"]
        
        entry = tk.Entry(self, font=TABLE_FONT, bg=TABLE_BG_COLOR, fg=TABLE_FG_COLOR, 
                        insertbackground=TABLE_FG_COLOR)
        
        x, y, w, h = self.bbox(item, column)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_value[int(column[1]) - 1])
        entry.select_range(0, tk.END)
        entry.focus()
        
        def on_enter(e):
            try:
                new_value = entry.get()
                values = list(current_value)
                col_idx = int(column[1]) - 1
                
                if column_name in ["Score", "Time"]:
                    new_value = int(new_value)
                elif column_name == "Date":
                    datetime.datetime.strptime(new_value, "%Y-%m-%d")
                
                values[col_idx] = new_value
                self.item(item, values=values)
                
                scores = load_highscores()
                scores[self.index(item)] = {
                    "date": values[0],
                    "level": values[1],
                    "score": int(values[2]),
                    "time": int(values[3]),
                    "name": values[4]
                }
                save_highscores(scores)
                
            except ValueError as e:
                messagebox.showerror("Invalid Input", str(e))
            finally:
                entry.destroy()
        
        entry.bind('<Return>', on_enter)
        entry.bind('<Escape>', lambda e: entry.destroy())
        entry.bind('<FocusOut>', lambda e: entry.destroy())

class HighscoresEditor(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Highscores Editor")
        self.geometry("800x600")
        
        # Make window resizable
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Create style for table only
        style = ttk.Style()
        style.configure("Custom.Treeview", 
                       background=TABLE_BG_COLOR, 
                       foreground=TABLE_FG_COLOR, 
                       fieldbackground=TABLE_BG_COLOR,
                       font=TABLE_FONT)
        style.configure("Custom.Treeview.Heading", 
                       font=("TkDefaultFont", 10, "bold"))  # Regular font for headers
        
        # Create main container
        main_container = ttk.Frame(self, padding="10")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # Create Treeview for scores
        self.scores_tree = EditableTreeview(
            main_container,
            columns=("Date", "Level", "Score", "Time", "Name"),
            show="headings",
            selectmode="browse",
            style="Custom.Treeview"
        )
        
        # Configure columns (initial setup)
        for col in self.scores_tree["columns"]:
            self.scores_tree.heading(col, text=col)
            self.scores_tree.column(col, width=100)  # Default width, will be adjusted
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_container, orient=tk.VERTICAL, command=self.scores_tree.yview)
        self.scores_tree.configure(yscrollcommand=scrollbar.set)
        
        # Button frame
        button_frame = ttk.Frame(main_container)
        
        # Buttons
        refresh_btn = ttk.Button(button_frame, text="Refresh", command=self.refresh_scores)
        add_btn = ttk.Button(button_frame, text="Add Score", command=self.show_add_dialog)
        remove_btn = ttk.Button(button_frame, text="Remove Selected", command=self.remove_score)
        
        # Layout
        self.scores_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        refresh_btn.pack(side=tk.LEFT, padx=5)
        add_btn.pack(side=tk.LEFT, padx=5)
        remove_btn.pack(side=tk.LEFT, padx=5)
        
        # Load initial scores and adjust columns
        self.refresh_scores()

    def refresh_scores(self):
        for item in self.scores_tree.get_children():
            self.scores_tree.delete(item)
        
        scores = load_highscores()
        
        # Insert all scores
        for score in scores:
            self.scores_tree.insert("", tk.END, values=(
                score["date"],
                score["level"],
                score["score"],
                score["time"],
                score["name"]
            ))
        
        # Adjust column widths based on content
        if scores:
            for col in self.scores_tree["columns"]:
                # Get width of column header
                header_width = len(col) * 10  # Approximate width based on font
                
                # Get maximum width of content in this column
                max_content_width = header_width
                col_idx = self.scores_tree["columns"].index(col)
                
                for item in self.scores_tree.get_children():
                    cell_value = str(self.scores_tree.item(item)["values"][col_idx])
                    content_width = len(cell_value) * 10  # Approximate width based on font
                    max_content_width = max(max_content_width, content_width)
                
                # Add padding and set column width
                self.scores_tree.column(col, width=max_content_width + 20)

    def show_add_dialog(self):
        dialog = AddScoreDialog(self)
        self.wait_window(dialog)
        self.refresh_scores()

    def remove_score(self):
        selected_item = self.scores_tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a score to remove.")
            return
        
        if messagebox.askyesno("Confirm Removal", "Are you sure you want to remove this score?"):
            scores = load_highscores()
            index = self.scores_tree.index(selected_item)
            scores.pop(index)
            save_highscores(scores)
            self.refresh_scores()

class AddScoreDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add New Score")
        self.geometry("300x250")
        
        self.transient(parent)
        self.grab_set()
        
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Create entry fields
        labels = ["Name:", "Level:", "Score:", "Time (seconds):"]
        self.vars = {
            "name": tk.StringVar(),
            "level": tk.StringVar(),
            "score": tk.StringVar(),
            "time": tk.StringVar()
        }
        
        for i, (label, var_name) in enumerate(zip(labels, self.vars.keys())):
            ttk.Label(main_frame, text=label).grid(row=i, column=0, sticky="w")
            ttk.Entry(main_frame, textvariable=self.vars[var_name]).grid(
                row=i, column=1, pady=5, padx=5, sticky="ew")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=len(labels), column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_score).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def save_score(self):
        try:
            name = self.vars["name"].get().strip()
            level = self.vars["level"].get().strip()
            score = int(self.vars["score"].get())
            time = int(self.vars["time"].get())
            
            if not name or not level:
                raise ValueError("Name and level cannot be empty")
            
            new_score = {
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "level": level,
                "score": score,
                "time": time,
                "name": name
            }
            
            scores = load_highscores()
            scores.append(new_score)
            save_highscores(scores)
            
            self.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

if __name__ == "__main__":
    app = HighscoresEditor()
    app.mainloop()