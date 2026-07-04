import os
os.environ["QT_DPI_AWARENESS"] = "none"

import customtkinter as ctk
from tkinter import ttk
import subprocess
import threading
import json
import sys
import time
from collections import deque
import re
from urllib.parse import urlparse

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class NetWatchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Net-Watch")
        self.root.geometry("1000x650")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        icon_path = resource_path("net-watch.ico")
        if os.path.exists(icon_path):
            self.root.after(200, lambda: self.root.iconbitmap(icon_path))
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        self.bg = "#202020"
        self.text = "#E0E0E0"
        self.panel = "#2A2A2D"
        self.border = "#575757"
        self.input_bg = "#202020"
        self.accent = "#7B2CBF"
        self.accent_hover = "#9D4EDD"
        self.disabled = "#575757"
        self.disabled_text = "#8A8A8A"
        self.cyan = "#00FFFF"
        self.font = ("Consolas", 11)
        self.font_bold = ("Consolas", 11, "bold")
        self.header_font = ("Consolas", 24, "bold")
        self.small_font = ("Consolas", 11)
        
        APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Dralder")
        if not os.path.exists(APP_DATA_DIR):
            os.makedirs(APP_DATA_DIR)
        self.data_file = os.path.join(APP_DATA_DIR, "net-watch.json")
        
        self.editing_ip = None
        self.targets = self.load_data()
        self.stats = {item["ip"]: {"history": deque([0]*40, maxlen=40), "lost": 0, "sent": 0, "last_vals": None, "tag": 'warning', "dirty": False} for item in self.targets}
        self.drag_data = {"item": None}
        self.ip_nodes = {}
        self.active_threads = {}
        self.running = True
        
        self.setup_ui()
        self.populate_initial_tree()
        self.start_threads()
        self.root.after(1000, self.ui_updater)

    def on_closing(self):
        self.running = False
        self.root.quit()
        self.root.destroy()
        os._exit(0)

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str):
                        return [{"ip": ip, "name": ""} for ip in data]
                    return data
            except:
                pass
        return [{"ip": "8.8.8.8", "name": "Google"}, {"ip": "1.1.1.1", "name": "Cloudflare"}]

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.targets, f)

    def setup_ui(self):
        self.root.configure(fg_color=self.bg)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self.root, fg_color=self.bg, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew", padx=20, pady=(10, 6))
        
        ctk.CTkLabel(self.header, text="NET-WATCH", font=self.header_font, text_color=self.accent).pack(side="left", padx=10)
        
        info_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        info_frame.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(info_frame, text="made by dralder", font=self.small_font, text_color=self.accent, height=14).pack(anchor="w", pady=0)
        ctk.CTkLabel(info_frame, text="v1.0.0", font=self.small_font, text_color=self.cyan, height=14).pack(anchor="w", pady=0)

        self.main_container = ctk.CTkFrame(self.root, fg_color=self.panel, corner_radius=8, border_color=self.border, border_width=1)
        self.main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background=self.input_bg,
            foreground=self.text,
            fieldbackground=self.input_bg,
            font=self.font,
            rowheight=28,
            borderwidth=0
        )
        style.map("Treeview", background=[("selected", self.accent)], foreground=[("selected", self.text)])
        style.configure(
            "Treeview.Heading",
            background=self.panel,
            foreground=self.text,
            relief="flat",
            font=self.font_bold
        )
        style.map("Treeview.Heading", background=[("active", self.accent_hover)], foreground=[("active", self.text)])

        self.tree_frame = ctk.CTkFrame(self.main_container, fg_color="transparent", border_width=0, corner_radius=8)
        self.tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)

        cols = ("NAME", "IP/HOST", "LATENCY", "JITTER", "LOSS", "STATUS")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        
        self.scrollbar = ctk.CTkScrollbar(
            self.tree_frame, 
            orientation="vertical", 
            command=self.tree.yview,
            fg_color=self.input_bg,
            button_color=self.border,
            button_hover_color=self.accent_hover,
            corner_radius=5
        )
        
        def autoscroll(first, last):
            self.scrollbar.set(first, last)
            if float(first) <= 0.0 and float(last) >= 1.0:
                self.scrollbar.grid_remove()
            else:
                self.scrollbar.grid(row=0, column=1, sticky="ns")
                
        self.tree.configure(yscrollcommand=autoscroll)
        
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c, False))
            self.tree.column(col, anchor="center", width=100)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_stop)

        self.context_menu = ctk.CTkFrame(self.root, width=140, height=90, fg_color=self.panel, border_color=self.border, border_width=1, corner_radius=8)
        ctk.CTkButton(self.context_menu, text="Edit", fg_color="transparent", text_color=self.text, hover_color=self.accent_hover, font=self.font_bold, corner_radius=5, command=self.prepare_edit).pack(expand=True, fill="both", padx=6, pady=(6, 2))
        ctk.CTkButton(self.context_menu, text="Remove", fg_color="transparent", text_color="#F44336", hover_color=self.accent_hover, font=self.font_bold, corner_radius=5, command=self.remove_node).pack(expand=True, fill="both", padx=6, pady=(2, 6))

        self.input_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.input_container.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.name_entry = ctk.CTkEntry(self.input_container, placeholder_text="Custom Name...", fg_color=self.input_bg, border_color=self.border, border_width=1, text_color=self.text, corner_radius=5, font=self.font)
        self.name_entry.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.ip_entry = ctk.CTkEntry(self.input_container, placeholder_text="Enter IP or Host...", fg_color=self.input_bg, border_color=self.border, border_width=1, text_color=self.text, corner_radius=5, font=self.font)
        self.ip_entry.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self.ip_entry.bind("<Return>", lambda e: self.handle_action())

        self.action_btn = ctk.CTkButton(self.input_container, text="ADD", fg_color=self.accent, text_color=self.text, hover_color=self.accent_hover, font=self.font_bold, corner_radius=5, command=self.handle_action)
        self.action_btn.pack(side="left", padx=(0, 6))

        self.cancel_btn = ctk.CTkButton(self.input_container, text="CANCEL", fg_color=self.panel, text_color=self.text, hover_color=self.accent_hover, border_color=self.border, border_width=1, font=self.font_bold, corner_radius=5, command=self.cancel_edit)
        
        self.tree.tag_configure('optimum', foreground='#4CAF50')
        self.tree.tag_configure('warning', foreground='#FFEB3B')
        self.tree.tag_configure('critical', foreground='#F44336')

    def sort_column(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        def parse_val(val):
            if col in ("LATENCY", "JITTER"):
                try:
                    return float(val.replace("ms", ""))
                except:
                    return float('inf') if not reverse else float('-inf')
            elif col == "LOSS":
                try:
                    return float(val.replace("%", ""))
                except:
                    return float('inf') if not reverse else float('-inf')
            return str(val).lower()

        l.sort(key=lambda t: parse_val(t[0]), reverse=reverse)

        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)

        new_targets = []
        for i in self.tree.get_children():
            vals = self.tree.item(i)['values']
            new_targets.append({"name": str(vals[0]), "ip": str(vals[1])})
        self.targets = new_targets
        self.save_data()

        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def populate_initial_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.ip_nodes.clear()
        for t in self.targets:
            item = self.tree.insert("", "end", values=(t["name"], t["ip"], "...", "...", "...", "LOADING"), tags=('warning',))
            self.ip_nodes[t["ip"]] = item

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.place(x=event.x_root - self.root.winfo_rootx(), y=event.y_root - self.root.winfo_rooty())
            self.context_menu.lift()
        else:
            self.context_menu.place_forget()

    def on_drag_start(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            return
        self.context_menu.place_forget()
        item = self.tree.identify_row(event.y)
        if item:
            self.drag_data["item"] = item

    def on_drag_motion(self, event):
        if not self.drag_data["item"]:
            return
        item = self.tree.identify_row(event.y)
        if item and item != self.drag_data["item"]:
            self.tree.move(self.drag_data["item"], self.tree.parent(item), self.tree.index(item))

    def on_drag_stop(self, event):
        if not self.drag_data["item"]:
            return
        self.drag_data["item"] = None
        new_targets = []
        for i in self.tree.get_children():
            vals = self.tree.item(i)['values']
            new_targets.append({"name": str(vals[0]), "ip": str(vals[1])})
        self.targets = new_targets
        self.save_data()

    def clean_host_input(self, input_str):
        raw = input_str.strip()
        if not raw:
            return ""
        
        if "://" in raw:
            parsed = urlparse(raw)
            host = parsed.hostname or parsed.netloc
        else:
            host = raw.split('/')[0]
            
        host = host.split(':')[0]
        
        if re.match(r'^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]))*$', host):
            return host
        return ""

    def handle_action(self):
        if self.editing_ip:
            self.save_edit()
        else:
            self.add_node()

    def add_node(self):
        raw_ip = self.ip_entry.get()
        ip = self.clean_host_input(raw_ip)
        name = self.name_entry.get().strip()
        
        if ip and not any(t["ip"] == ip for t in self.targets):
            self.targets.append({"ip": ip, "name": name})
            self.stats[ip] = {"history": deque([0]*40, maxlen=40), "lost": 0, "sent": 0, "last_vals": None, "tag": 'warning', "dirty": False}
            item = self.tree.insert("", "end", values=(name, ip, "...", "...", "...", "LOADING"), tags=('warning',))
            self.ip_nodes[ip] = item
            self.save_data()
        
        self.ip_entry.delete(0, 'end')
        self.name_entry.delete(0, 'end')

    def remove_node(self):
        selected = self.tree.selection()
        if selected:
            ip = str(self.tree.item(selected[0])['values'][1])
            self.targets = [t for t in self.targets if t["ip"] != ip]
            if ip in self.stats:
                del self.stats[ip]
            if ip in self.ip_nodes:
                del self.ip_nodes[ip]
            self.tree.delete(selected[0])
            self.save_data()
            self.context_menu.place_forget()
            if self.editing_ip == ip:
                self.cancel_edit()

    def prepare_edit(self):
        selected = self.tree.selection()
        if not selected:
            return
        vals = self.tree.item(selected[0])['values']
        self.editing_ip = str(vals[1])
        self.name_entry.delete(0, 'end')
        self.name_entry.insert(0, str(vals[0]))
        self.ip_entry.delete(0, 'end')
        self.ip_entry.insert(0, str(vals[1]))
        self.action_btn.configure(text="SAVE", fg_color=self.accent, text_color=self.text)
        self.cancel_btn.pack(side="left")
        self.context_menu.place_forget()

    def save_edit(self):
        new_name = self.name_entry.get().strip()
        raw_ip = self.ip_entry.get()
        new_ip = self.clean_host_input(raw_ip)
        
        if new_ip:
            for t in self.targets:
                if t["ip"] == self.editing_ip:
                    t["name"] = new_name
                    t["ip"] = new_ip
                    
            if new_ip != self.editing_ip:
                if self.editing_ip in self.stats:
                    self.stats[new_ip] = self.stats.pop(self.editing_ip)
                else:
                    self.stats[new_ip] = {"history": deque([0]*40, maxlen=40), "lost": 0, "sent": 0, "last_vals": None, "tag": 'warning', "dirty": False}
                if self.editing_ip in self.ip_nodes:
                    self.ip_nodes[new_ip] = self.ip_nodes.pop(self.editing_ip)
            else:
                if self.editing_ip in self.stats:
                    self.stats[self.editing_ip]["dirty"] = True
                    
            self.save_data()
            
        self.cancel_edit()

    def cancel_edit(self):
        self.editing_ip = None
        self.name_entry.delete(0, 'end')
        self.ip_entry.delete(0, 'end')
        self.action_btn.configure(text="ADD", fg_color=self.accent, text_color=self.text)
        self.cancel_btn.pack_forget()

    def ui_updater(self):
        if not self.running:
            return

        for ip, stat in self.stats.items():
            if stat.get("dirty"):
                vals = stat.get("last_vals")
                tag = stat.get("tag")
                if vals:
                    item = self.ip_nodes.get(ip)
                    if item and self.tree.exists(item):
                        self.tree.item(item, values=vals, tags=(tag,))
                stat["dirty"] = False

        self.root.after(1000, self.ui_updater)

    def get_ping(self, ip):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            out = subprocess.check_output(['ping', '-n', '1', '-w', '1000', ip], startupinfo=si, stderr=subprocess.DEVNULL, universal_newlines=True)
            if "time=" in out:
                return float(out.split("time=")[1].split("ms")[0].strip())
            elif "time<" in out:
                return float(out.split("time<")[1].split("ms")[0].strip())
        except:
            pass
        return None

    def run_worker(self, ip):
        while self.running and any(t["ip"] == ip for t in self.targets):
            lat = self.get_ping(ip)
            if ip not in self.stats:
                break
            
            self.stats[ip]["sent"] += 1
            if lat is not None:
                self.stats[ip]["history"].append(lat)
            else:
                self.stats[ip]["lost"] += 1
                self.stats[ip]["history"].append(0)
                
            hist = [x for x in self.stats[ip]["history"] if x > 0]
            jit = sum(abs(hist[i] - hist[i-1]) for i in range(1, len(hist))) / (len(hist)-1) if len(hist) > 1 else 0
            loss = (self.stats[ip]["lost"] / self.stats[ip]["sent"]) * 100
            
            tag = 'critical'
            if lat:
                if lat < 60:
                    tag = 'optimum'
                elif lat < 150:
                    tag = 'warning'
                
            status = "ACTIVE" if tag == 'optimum' else "UNSTABLE" if tag == 'warning' else "DROPPED"
            current_name = next((t["name"] for t in self.targets if t["ip"] == ip), "")
            
            vals = (current_name, ip, f"{int(lat)}ms" if lat else "N/A", f"{int(jit)}ms" if jit else "--", f"{loss:.1f}%", status)
            
            self.stats[ip]["last_vals"] = vals
            self.stats[ip]["tag"] = tag
            self.stats[ip]["dirty"] = True
            
            time.sleep(2.0)

    def orchestrator(self):
        while self.running:
            for target in list(self.targets):
                ip = target["ip"]
                if ip not in self.active_threads or not self.active_threads[ip].is_alive():
                    t = threading.Thread(target=self.run_worker, args=(ip,), daemon=True)
                    t.start()
                    self.active_threads[ip] = t
            time.sleep(3.0)

    def start_threads(self):
        threading.Thread(target=self.orchestrator, daemon=True).start()

if __name__ == "__main__":
    app = ctk.CTk()
    app.configure(fg_color="#202020")
    NetWatchApp(app)
    app.mainloop()
