import tkinter as tk
from tkinter import ttk, messagebox
import json
from typing import Dict, Any
import copy

class LevelEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Level Editor")
        
        # Load initial data
        self.levels = self.load_levels()
        self.current_level = None
        
        self.setup_ui()
        
    def load_levels(self) -> list:
        try:
            with open('levels.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
            
    def save_levels(self):
        try:
            with open('levels.json', 'w') as f:
                json.dump(self.levels, f, indent=2)
            messagebox.showinfo("Success", "Levels saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save levels: {str(e)}")
    
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Level selection
        level_frame = ttk.LabelFrame(main_frame, text="Level Selection", padding="5")
        level_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.level_var = tk.StringVar()
        self.level_dropdown = ttk.Combobox(level_frame, textvariable=self.level_var)
        self.level_dropdown['values'] = [level['level'] for level in self.levels]
        self.level_dropdown.grid(row=0, column=0, padx=5)
        self.level_dropdown.bind('<<ComboboxSelected>>', self.on_level_selected)
        
        ttk.Button(level_frame, text="New Level", command=self.create_new_level).grid(row=0, column=1, padx=5)
        ttk.Button(level_frame, text="Save All", command=self.save_levels).grid(row=0, column=2, padx=5)
        
        # Level properties
        props_frame = ttk.LabelFrame(main_frame, text="Level Properties", padding="5")
        props_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Basic properties
        self.level_name_var = tk.StringVar()
        ttk.Label(props_frame, text="Level Name:").grid(row=0, column=0, sticky=tk.W)
        self.level_name_entry = ttk.Entry(props_frame, textvariable=self.level_name_var)
        self.level_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        self.winning_level_var = tk.IntVar()
        ttk.Label(props_frame, text="Winning Level:").grid(row=1, column=0, sticky=tk.W)
        self.winning_level_spinbox = ttk.Spinbox(props_frame, from_=1, to=100, textvariable=self.winning_level_var)
        self.winning_level_spinbox.grid(row=1, column=1, sticky=(tk.W, tk.E))
        
        # Toggles
        self.pull_blocks_var = tk.BooleanVar()
        self.speed_up_var = tk.BooleanVar()
        self.explosive_blocks_var = tk.BooleanVar()
        
        ttk.Checkbutton(props_frame, text="Pull Blocks", variable=self.pull_blocks_var).grid(row=2, column=0, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(props_frame, text="Speed Up", variable=self.speed_up_var).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(props_frame, text="Explosive Blocks", variable=self.explosive_blocks_var).grid(row=4, column=0, columnspan=2, sticky=tk.W)
        
        # Enemies frame
        enemies_frame = ttk.LabelFrame(main_frame, text="Enemies", padding="5")
        enemies_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        
        # Hunter properties
        hunter_frame = ttk.LabelFrame(enemies_frame, text="Hunter", padding="5")
        hunter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.hunter_count_var = tk.IntVar()
        self.hunter_speed_var = tk.IntVar()
        self.hunter_accuracy_var = tk.IntVar()
        
        ttk.Label(hunter_frame, text="Count:").grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(hunter_frame, from_=0, to=10, textvariable=self.hunter_count_var).grid(row=0, column=1)
        
        ttk.Label(hunter_frame, text="Speed (ms):").grid(row=1, column=0, sticky=tk.W)
        ttk.Spinbox(hunter_frame, from_=100, to=2000, increment=100, textvariable=self.hunter_speed_var).grid(row=1, column=1)
        
        ttk.Label(hunter_frame, text="Accuracy (%):").grid(row=2, column=0, sticky=tk.W)
        ttk.Spinbox(hunter_frame, from_=0, to=100, textvariable=self.hunter_accuracy_var).grid(row=2, column=1)
        
        # Egg properties
        egg_frame = ttk.LabelFrame(enemies_frame, text="Egg", padding="5")
        egg_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.egg_count_var = tk.IntVar()
        self.egg_incubation_var = tk.IntVar()
        
        ttk.Label(egg_frame, text="Count:").grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(egg_frame, from_=0, to=10, textvariable=self.egg_count_var).grid(row=0, column=1)
        
        ttk.Label(egg_frame, text="Incubation (s):").grid(row=1, column=0, sticky=tk.W)
        ttk.Spinbox(egg_frame, from_=0, to=100, textvariable=self.egg_incubation_var).grid(row=1, column=1)
        
        # Bind update events
        for var in [self.level_name_var, self.winning_level_var, self.pull_blocks_var,
                   self.speed_up_var, self.explosive_blocks_var, self.hunter_count_var,
                   self.hunter_speed_var, self.hunter_accuracy_var, self.egg_count_var,
                   self.egg_incubation_var]:
            var.trace_add('write', self.update_current_level)
    
    def create_new_level(self):
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
        self.level_dropdown['values'] = [level['level'] for level in self.levels]
        self.level_dropdown.set(new_level['level'])
        self.load_level_data(new_level)
    
    def on_level_selected(self, event):
        selected = self.level_var.get()
        level_data = next((level for level in self.levels if level['level'] == selected), None)
        if level_data:
            self.load_level_data(level_data)
    
    def load_level_data(self, level_data: Dict[str, Any]):
        self.current_level = level_data
        
        # Set basic properties
        self.level_name_var.set(level_data['level'])
        self.winning_level_var.set(level_data['winning_level'])
        self.pull_blocks_var.set(level_data['pull_blocks'])
        self.speed_up_var.set(level_data['speed_up'])
        self.explosive_blocks_var.set(level_data['explosive_blocks'])
        
        # Set hunter properties
        hunter_data = level_data['enemies'].get('hunter', {})
        self.hunter_count_var.set(hunter_data.get('count', 0))
        self.hunter_speed_var.set(hunter_data.get('speed_ms', 1100))
        self.hunter_accuracy_var.set(hunter_data.get('accuracy', 100))
        
        # Set egg properties
        egg_data = level_data['enemies'].get('egg', {})
        self.egg_count_var.set(egg_data.get('count', 0))
        self.egg_incubation_var.set(egg_data.get('incubation_s', 0))
    
    def update_current_level(self, *args):
        if not self.current_level:
            return
            
        try:
            # Update basic properties
            old_level_name = self.current_level['level']
            self.current_level['level'] = self.level_name_var.get()
            self.current_level['winning_level'] = self.winning_level_var.get()
            self.current_level['pull_blocks'] = self.pull_blocks_var.get()
            self.current_level['speed_up'] = self.speed_up_var.get()
            self.current_level['explosive_blocks'] = self.explosive_blocks_var.get()
            
            # Update hunter properties
            if 'hunter' not in self.current_level['enemies']:
                self.current_level['enemies']['hunter'] = {}
            self.current_level['enemies']['hunter'].update({
                'count': self.hunter_count_var.get(),
                'speed_ms': self.hunter_speed_var.get(),
                'accuracy': self.hunter_accuracy_var.get()
            })
            
            # Update egg properties
            if self.egg_count_var.get() > 0:
                if 'egg' not in self.current_level['enemies']:
                    self.current_level['enemies']['egg'] = {'hatches_into': 'pusher'}
                self.current_level['enemies']['egg'].update({
                    'count': self.egg_count_var.get(),
                    'incubation_s': self.egg_incubation_var.get()
                })
            elif 'egg' in self.current_level['enemies']:
                del self.current_level['enemies']['egg']
            
            # Update dropdown if level name changed
            if old_level_name != self.current_level['level']:
                current_values = list(self.level_dropdown['values'])
                index = current_values.index(old_level_name)
                current_values[index] = self.current_level['level']
                self.level_dropdown['values'] = current_values
                self.level_dropdown.set(self.current_level['level'])
                
        except Exception as e:
            print(f"Error updating level: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LevelEditor(root)
    root.mainloop()