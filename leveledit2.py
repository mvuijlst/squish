import tkinter as tk
from tkinter import ttk, messagebox
import json
from typing import Dict, Any
import copy

class SpreadsheetLevelEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Level Editor - Spreadsheet View")
        
        # Load initial data
        self.levels = self.load_levels()
        self.setup_ui()
        
    def load_levels(self) -> list:
        try:
            with open('levels.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
            
    def save_levels(self):
        try:
            self.update_all_levels()
            with open('levels.json', 'w') as f:
                json.dump(self.levels, f, indent=2)
            messagebox.showinfo("Success", "Levels saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save levels: {str(e)}")

    def setup_ui(self):
        # Main container with scrollbar
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)
        scrollbar.grid(row=1, column=0, sticky="ew")
        
        canvas.configure(xscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        
        # Frame for the table
        self.table_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.table_frame, anchor="nw")
        
        # Save button at the top
        ttk.Button(self.table_frame, text="Save All", command=self.save_levels).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(self.table_frame, text="Add Level", command=self.add_new_level).grid(row=0, column=1, padx=5, pady=5)
        
        # Properties list (first column)
        properties = [
            ("Level Name", "level", "entry"),
            ("Winning Level", "winning_level", "spinbox", 1, 100),
            ("Pull Blocks", "pull_blocks", "checkbox"),
            ("Speed Up", "speed_up", "checkbox"),
            ("Explosive Blocks", "explosive_blocks", "checkbox"),
            ("Hunter Count", "enemies.hunter.count", "spinbox", 0, 10),
            ("Hunter Speed (ms)", "enemies.hunter.speed_ms", "spinbox", 100, 2000),
            ("Hunter Accuracy (%)", "enemies.hunter.accuracy", "spinbox", 0, 100),
            ("Hunter Speed Variability", "enemies.hunter.speed_variability", "spinbox", 0, 100),
            ("Hunter Mutation Ratio", "enemies.hunter.mutation_ratio", "spinbox", 0, 1),
            ("Egg Count", "enemies.egg.count", "spinbox", 0, 10),
            ("Egg Incubation (s)", "enemies.egg.incubation_s", "spinbox", 0, 100)
        ]
        
        # Create property labels
        for row, prop in enumerate(properties, start=1):
            ttk.Label(self.table_frame, text=prop[0]).grid(row=row, column=0, padx=5, pady=2, sticky="e")
        
        # Create input fields for each level
        self.level_widgets = []
        for col, level_data in enumerate(self.levels, start=1):
            level_inputs = {}
            for row, prop in enumerate(properties, start=1):
                prop_path = prop[1]
                widget_type = prop[2]
                args = prop[3:] if len(prop) > 3 else []
                
                value = self.get_nested_value(level_data, prop_path)
                widget = self.create_widget(widget_type, value, *args)
                widget.grid(row=row, column=col, padx=5, pady=2)
                level_inputs[prop_path] = widget
            self.level_widgets.append(level_inputs)
            
        # Update canvas scroll region
        self.table_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Make main_frame expandable
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
    def create_widget(self, widget_type, value, *args):
        if widget_type == "entry":
            widget = ttk.Entry(self.table_frame)
            widget.insert(0, str(value))
            return widget
        elif widget_type == "spinbox":
            min_val, max_val = args
            widget = ttk.Spinbox(self.table_frame, from_=min_val, to=max_val)
            widget.set(value)
            return widget
        elif widget_type == "checkbox":
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(self.table_frame, variable=var)
            # Store the variable in the widget for later access
            widget.var = var
            return widget
            
    def get_nested_value(self, data: Dict, path: str) -> Any:
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, {})
            else:
                return None
        return value
        
    def set_nested_value(self, data: Dict, path: str, value: Any):
        keys = path.split('.')
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        
    def update_all_levels(self):
        for level_idx, level_inputs in enumerate(self.level_widgets):
            level_data = self.levels[level_idx]
            for prop_path, widget in level_inputs.items():
                if isinstance(widget, ttk.Checkbutton):
                    value = widget.var.get()
                else:
                    value = widget.get()
                    # Convert to appropriate type
                    if prop_path in ['winning_level', 'enemies.hunter.count', 
                                   'enemies.hunter.speed_ms', 'enemies.hunter.accuracy',
                                   'enemies.hunter.speed_variability', 'enemies.egg.count',
                                   'enemies.egg.incubation_s']:
                        value = int(float(value))
                    elif prop_path == 'enemies.hunter.mutation_ratio':
                        value = float(value)
                self.set_nested_value(level_data, prop_path, value)
                
    def add_new_level(self):
        new_level = {
            "level": f"Level_{len(self.levels) + 1}",
            "pull_blocks": False,
            "speed_up": False,
            "explosive_blocks": False,
            "winning_level": 1,
            "enemies": {
                "hunter": {
                    "count": 1,
                    "speed_ms": 1100,
                    "accuracy": 100,
                    "speed_variability": 0,
                    "mutation_ratio": 0
                }
            }
        }
        self.levels.append(new_level)
        # Recreate the entire UI to show the new level
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.setup_ui()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")
    app = SpreadsheetLevelEditor(root)
    root.mainloop()