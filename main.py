import customtkinter as ctk
from tkinter import messagebox
import threading
import sys
import os
from datetime import datetime
from optimizer import SystemOptimizer, ProcessOptimizer
from updater import Updater, get_version
import psutil


ctk.set_appearance_mode("dark")


NEON_GREEN = "#00ff41"
NEON_CYAN = "#00f5ff"
NEON_PINK = "#ff00ff"
NEON_PURPLE = "#bf00ff"
NEON_RED = "#ff0040"
NEON_YELLOW = "#f0ff00"
NEON_ORANGE = "#ff6600"

BG_DARK = "#0d0d0d"
BG_DARKER = "#050505"
BG_PANEL = "#0a0a0a"
BG_CARD = "#111111"
BORDER_GLOW = "#00ff41"
TEXT_MAIN = "#00ff41"
TEXT_DIM = "#00aa2a"
TEXT_BRIGHT = "#33ff66"


class NeonFrame(ctk.CTkFrame):
    
    def __init__(self, master, glow_color=NEON_GREEN, **kwargs):
        kwargs.setdefault('fg_color', BG_CARD)
        kwargs.setdefault('corner_radius', 8)
        kwargs.setdefault('border_width', 1)
        kwargs.setdefault('border_color', glow_color)
        super().__init__(master, **kwargs)


class GlitchLabel(ctk.CTkLabel):
    
    def __init__(self, master, glitch=False, **kwargs):
        kwargs.setdefault('text_color', NEON_GREEN)
        super().__init__(master, **kwargs)


class TerminalText(ctk.CTkTextbox):
    
    def __init__(self, master, **kwargs):
        kwargs.setdefault('fg_color', BG_DARKER)
        kwargs.setdefault('text_color', NEON_GREEN)
        kwargs.setdefault('font', ctk.CTkFont(family="Consolas", size=11))
        kwargs.setdefault('border_width', 2)
        kwargs.setdefault('border_color', NEON_GREEN)
        super().__init__(master, **kwargs)


class CyberButton(ctk.CTkButton):
    
    def __init__(self, master, neon_color=NEON_GREEN, **kwargs):
        kwargs.setdefault('fg_color', "transparent")
        kwargs.setdefault('border_width', 2)
        kwargs.setdefault('border_color', neon_color)
        kwargs.setdefault('text_color', neon_color)
        kwargs.setdefault('hover_color', neon_color)
        kwargs.setdefault('font', ctk.CTkFont(family="Consolas", size=12, weight="bold"))
        kwargs.setdefault('corner_radius', 6)
        super().__init__(master, **kwargs)


class SystemCard(NeonFrame):
    
    def __init__(self, master, title: str, value: str, icon: str = ">", glow=NEON_GREEN, **kwargs):
        super().__init__(master, glow_color=glow, **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(10, 3), sticky="w")
        
        ctk.CTkLabel(
            header,
            text=f"[{icon}]",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=glow
        ).pack(side="left", padx=(0, 6))
        
        ctk.CTkLabel(
            header,
            text=title.upper(),
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM
        ).pack(side="left")
        
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            text_color=glow
        )
        self.value_label.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
    
    def update_value(self, value: str):
        self.value_label.configure(text=value)


class ProgressCard(NeonFrame):
    
    def __init__(self, master, title: str, value: float, glow=NEON_GREEN, **kwargs):
        super().__init__(master, glow_color=glow, **kwargs)
        self._glow = glow
        
        self.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            self,
            text=f"// {title}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM
        ).grid(row=0, column=0, padx=10, pady=(10, 3), sticky="w")
        
        self.progress = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=2,
            progress_color=glow,
            fg_color=BG_DARKER,
            border_width=1,
            border_color=glow
        )
        self.progress.grid(row=1, column=0, padx=10, pady=3, sticky="ew")
        self.progress.set(value / 100)
        
        self.value_label = ctk.CTkLabel(
            self,
            text=f"{value:.1f}%",
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color=glow
        )
        self.value_label.grid(row=2, column=0, padx=10, pady=(3, 10), sticky="w")
    
    def update_value(self, value: float, color: str = None):
        self.progress.set(value / 100)
        self.value_label.configure(text=f"{value:.1f}%")
        if color:
            self.progress.configure(progress_color=color, border_color=color)
            self.value_label.configure(text_color=color)
            self.configure(border_color=color)


class HackerToolButton(NeonFrame):
    
    def __init__(self, master, title: str, desc: str, icon: str, command, glow=NEON_GREEN, **kwargs):
        super().__init__(master, glow_color=glow, **kwargs)
        
        self.grid_columnconfigure(1, weight=1)
        self._command = command
        
        self.bind("<Button-1>", self._on_click)
        
        self.icon_label = ctk.CTkLabel(
            self,
            text=f"[{icon}]",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=glow
        )
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        
        self.title_label = ctk.CTkLabel(
            self,
            text=f"> {title}",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=glow
        )
        self.title_label.grid(row=0, column=1, padx=(0, 10), pady=(10, 0), sticky="sw")
        
        self.desc_label = ctk.CTkLabel(
            self,
            text=f"  {desc}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM
        )
        self.desc_label.grid(row=1, column=1, padx=(0, 8), pady=(0, 8), sticky="nw")
        
        self.icon_label.bind("<Button-1>", self._on_click)
        self.title_label.bind("<Button-1>", self._on_click)
        self.desc_label.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        if self._command:
            self._command()


class OptimizerApp(ctk.CTk):
    
    def __init__(self):
        super().__init__()
        
        self.title("◢ YALOKGAR // SYSTEM OPTIMIZER ◣")
        self.geometry("1280x850")
        self.minsize(800, 500)
        
        self.configure(fg_color=BG_DARK)
        
        self._setup_grid()
        self._create_sidebar()
        self._create_main_area()
        
        self.optimizer = SystemOptimizer(log_callback=self._log)
        self.process_optimizer = ProcessOptimizer(log_callback=self._log)
        self.updater = Updater(log_callback=self._log)
        
        self._is_running = False
        self._update_system_info()
        self._start_monitoring()
    
    def _setup_grid(self):
        self.grid_columnconfigure(0, weight=0, minsize=280)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
    
    def _create_sidebar(self):
        self.sidebar = ctk.CTkScrollableFrame(
            self, 
            fg_color=BG_PANEL, 
            width=280, 
            corner_radius=0,
            scrollbar_button_color=NEON_GREEN,
            scrollbar_button_hover_color=NEON_CYAN
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=15, pady=(20, 5))
        
        GlitchLabel(
            logo_frame,
            text="◢◤ YALOKGAR ◥◣",
            font=ctk.CTkFont(family="Consolas", size=22, weight="bold"),
            text_color=NEON_GREEN,
            glitch=True
        ).pack(anchor="center")
        
        ctk.CTkLabel(
            logo_frame,
            text=f"[ SYSTEM OPTIMIZER v{get_version()} ]",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM
        ).pack(anchor="center", pady=(2, 0))
        
        ctk.CTkLabel(
            logo_frame,
            text="━" * 24,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=NEON_GREEN
        ).pack(anchor="center", pady=(8, 0))
        
        self.full_opt_btn = CyberButton(
            self.sidebar,
            text="◆ ПОЛНАЯ ОПТИМИЗАЦИЯ ◆",
            neon_color=NEON_CYAN,
            height=45,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            command=self._run_full_optimization
        )
        self.full_opt_btn.pack(fill="x", padx=15, pady=(15, 8))
        
        buttons_config = [
            ("⌂ Быстрая очистка", self._run_quick_clean, NEON_GREEN),
            ("◈ Оптимизация RAM", self._run_ram_optimization, NEON_GREEN),
            ("▣ Игровой режим", self._run_game_mode, NEON_PURPLE),  
            ("◎ Оптимизация сети", self._run_network_optimization, NEON_CYAN),
            ("⚡ Высокая мощность", self._run_power_optimization, NEON_YELLOW),
        ]
        
        for i, (text, cmd, color) in enumerate(buttons_config):
            btn = CyberButton(
                self.sidebar,
                text=text,
                neon_color=color,
                height=38,
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                command=cmd
            )
            btn.pack(fill="x", padx=15, pady=4)
            setattr(self, f'btn_{i}', btn)
        
        ctk.CTkLabel(
            self.sidebar,
            text="━" * 24,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM
        ).pack(pady=(10, 5))
        
        self.benchmark_btn = CyberButton(
            self.sidebar,
            text="📊 БЕНЧМАРК",
            neon_color=NEON_CYAN,
            height=35,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            command=self._run_benchmark
        )
        self.benchmark_btn.pack(fill="x", padx=15, pady=3)
        
        self.rollback_btn = CyberButton(
            self.sidebar,
            text="↩ ОТКАТ ИЗМЕНЕНИЙ",
            neon_color=NEON_RED,
            height=35,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            command=self._run_rollback
        )
        self.rollback_btn.pack(fill="x", padx=15, pady=3)
        
        self.open_logs_btn = CyberButton(
            self.sidebar,
            text="📄 ОТКРЫТЬ ЛОГИ",
            neon_color=NEON_ORANGE,
            height=35,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            command=self._open_logs
        )
        self.open_logs_btn.pack(fill="x", padx=15, pady=3)
        
        self.update_btn = CyberButton(
            self.sidebar,
            text="🔄 ПРОВЕРИТЬ ОБНОВЛЕНИЯ",
            neon_color=NEON_GREEN,
            height=35,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            command=self._check_updates
        )
        self.update_btn.pack(fill="x", padx=15, pady=3)
        
        stats_frame = NeonFrame(self.sidebar, glow_color=NEON_GREEN)
        stats_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            stats_frame,
            text="// SYSTEM STATUS",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM
        ).pack(padx=12, pady=(10, 4), anchor="w")
        
        self.status_label = ctk.CTkLabel(
            stats_frame,
            text="[■■■■■■■■■■] READY",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=NEON_GREEN
        )
        self.status_label.pack(padx=12, pady=(0, 10), anchor="w")
        
        author_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        author_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkLabel(
            author_frame,
            text="━" * 24,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM
        ).pack()
        
        ctk.CTkLabel(
            author_frame,
            text="coded by YALOKGAR",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=NEON_PINK
        ).pack(pady=(5, 0))
        
        ctk.CTkLabel(
            author_frame,
            text="github.com/YALOKGARua",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM
        ).pack()
    
    def _create_main_area(self):
        self.main_area = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=NEON_GREEN, scrollbar_button_hover_color=NEON_CYAN)
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_area.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="cards")
        
        header_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        
        GlitchLabel(
            header_frame,
            text="◢ CONTROL PANEL ◣",
            font=ctk.CTkFont(family="Consolas", size=24, weight="bold"),
            text_color=NEON_GREEN,
            glitch=True
        ).pack(side="left")
        
        self.time_label = ctk.CTkLabel(
            header_frame,
            text=f"[SESSION: {datetime.now().strftime('%H:%M')}]",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=TEXT_DIM
        )
        self.time_label.pack(side="right")
        
        self.cpu_card = SystemCard(self.main_area, "PROCESSOR", "—", "CPU", NEON_CYAN)
        self.cpu_card.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")
        
        self.ram_card = SystemCard(self.main_area, "MEMORY", "—", "RAM", NEON_PURPLE)
        self.ram_card.grid(row=1, column=1, padx=3, pady=3, sticky="nsew")
        
        self.disk_card = SystemCard(self.main_area, "STORAGE", "—", "HDD", NEON_PINK)
        self.disk_card.grid(row=1, column=2, padx=3, pady=3, sticky="nsew")
        
        self.gpu_card = SystemCard(self.main_area, "GRAPHICS", "—", "GPU", NEON_GREEN)
        self.gpu_card.grid(row=1, column=3, padx=3, pady=3, sticky="nsew")
        
        progress_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        progress_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=6)
        progress_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="progress")
        
        self.cpu_progress = ProgressCard(progress_frame, "CPU_LOAD", 0, NEON_CYAN)
        self.cpu_progress.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")
        
        self.ram_progress = ProgressCard(progress_frame, "RAM_USAGE", 0, NEON_PURPLE)
        self.ram_progress.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")
        
        self.disk_progress = ProgressCard(progress_frame, "DISK_FILL", 0, NEON_PINK)
        self.disk_progress.grid(row=0, column=2, padx=3, pady=3, sticky="nsew")
        
        ctk.CTkLabel(
            self.main_area,
            text="◢ OPTIMIZATION TOOLS ◣",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=NEON_GREEN
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(15, 8))
        
        tools_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        tools_frame.grid(row=4, column=0, columnspan=4, sticky="ew")
        tools_frame.grid_columnconfigure((0, 1), weight=1, uniform="tools")
        
        tools = [
            ("ULTIMATE_OPT", "Max FPS + Min Input Lag", "★", self._run_ultimate_optimization, NEON_CYAN),
            ("INPUT_LAG_FIX", "Game priority + Responsiveness", "◈", self._run_input_lag, NEON_PURPLE),
            ("GPU_VRAM", "Очистка видеопамяти", "◇", self._run_gpu_vram_clean, NEON_CYAN),
            ("TASK_SCHED", "Отключить задачи Windows", "▦", self._run_disable_tasks, NEON_PURPLE),
            ("CPU_AFFINITY", "Оптимизация ядер CPU", "◉", self._run_cpu_affinity, NEON_GREEN),
            ("PREFETCH", "Отключить Prefetch/SysMain", "◐", self._run_disable_prefetch, NEON_YELLOW),
            ("SSD_TRIM", "Оптимизация SSD (TRIM)", "▣", self._run_trim, NEON_PINK),
            ("MOUSE_RAW", "Disable acceleration", "◎", self._run_mouse_optimization, NEON_GREEN),
            ("FULLSCREEN_FIX", "Disable FSO + Game DVR", "◆", self._run_fullscreen_fix, NEON_YELLOW),
            ("DISABLE_HPET", "Lower timer latency", "▢", self._run_disable_hpet, NEON_PINK),
            ("GPU_SCHEDULE", "Hardware GPU Scheduling", "⟳", self._run_gpu_scheduling, NEON_CYAN),
            ("CORE_UNPARK", "100% CPU cores active", "●", self._run_core_unpark, NEON_GREEN),
            ("KILL_BG_APPS", "Disable background apps", "✕", self._run_disable_bg_apps, NEON_RED),
            ("KILL_SERVICES", "Disable telemetry", "⚡", self._run_services_optimization, NEON_YELLOW),
        ]
        
        for i, (title, desc, icon, cmd, color) in enumerate(tools):
            row = i // 2
            col = i % 2
            HackerToolButton(
                tools_frame, title, desc, icon, cmd, glow=color
            ).grid(row=row, column=col, padx=3, pady=3, sticky="ew")
        
        self._create_terminal()
    
    def _create_terminal(self):
        ctk.CTkLabel(
            self.main_area,
            text="◢ TERMINAL OUTPUT ◣",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=NEON_GREEN
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(15, 8))
        
        log_frame = NeonFrame(self.main_area, glow_color=NEON_GREEN)
        log_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_text = TerminalText(log_frame, height=120, wrap="word")
        self.log_text.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self._log("╔═══════════════════════════════════════════════╗")
        self._log("║  YALOKGAR SYSTEM OPTIMIZER v2.0               ║")
        self._log("║  [READY] All modules loaded                   ║")
        self._log("╚═══════════════════════════════════════════════╝")
        self._log("> Awaiting commands...")
    
    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if message.startswith("╔") or message.startswith("║") or message.startswith("╚") or message == "":
            formatted = f"{message}\n"
        else:
            formatted = f"[{timestamp}] {message}\n"
        
        if hasattr(self, 'log_text'):
            self.log_text.insert("end", formatted)
            self.log_text.see("end")
    
    def _update_system_info(self):
        try:
            info = self.optimizer.get_system_info()
            
            self.cpu_card.update_value(f"{info['cpu_usage']:.0f}%")
            self.ram_card.update_value(f"{info['ram_used_gb']:.1f} GB")
            self.disk_card.update_value(f"{info['disk_free_gb']:.0f} GB FREE")
            
            if info['gpu_name']:
                gpu_short = info['gpu_name'][:20] + "..." if len(info['gpu_name']) > 20 else info['gpu_name']
                self.gpu_card.update_value(gpu_short)
            
            cpu_color = NEON_CYAN if info['cpu_usage'] < 70 else (NEON_YELLOW if info['cpu_usage'] < 90 else NEON_RED)
            ram_color = NEON_PURPLE if info['ram_percent'] < 70 else (NEON_YELLOW if info['ram_percent'] < 90 else NEON_RED)
            disk_color = NEON_PINK if info['disk_percent'] < 80 else (NEON_YELLOW if info['disk_percent'] < 90 else NEON_RED)
            
            self.cpu_progress.update_value(info['cpu_usage'], cpu_color)
            self.ram_progress.update_value(info['ram_percent'], ram_color)
            self.disk_progress.update_value(info['disk_percent'], disk_color)
            
            
        except Exception:
            pass
    
    def _start_monitoring(self):
        def update_loop():
            try:
                self._update_system_info()
            except:
                pass
            self.after(2000, update_loop)
        
        self.after(1000, update_loop)
    
    def _run_in_thread(self, func, button=None):
        if self._is_running:
            self._log("⚠ [WARN] Operation already in progress...")
            return
        
        def task():
            self._is_running = True
            self.status_label.configure(text="[▓▓▓▓▓░░░░░] WORKING", text_color=NEON_YELLOW)
            if button:
                button.configure(state="disabled")
            
            try:
                func()
                self.status_label.configure(text="[■■■■■■■■■■] COMPLETE", text_color=NEON_GREEN)
            except Exception as e:
                self._log(f"✕ [ERROR] {e}")
                self.status_label.configure(text="[XXXXXXXXXX] ERROR", text_color=NEON_RED)
            finally:
                self._is_running = False
                if button:
                    self.after(0, lambda: button.configure(state="normal"))
                self.after(2000, lambda: self.status_label.configure(text="[■■■■■■■■■■] READY", text_color=NEON_GREEN))
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
    
    def _run_full_optimization(self):
        self._log("> Executing FULL_OPTIMIZATION protocol...")
        self._run_in_thread(lambda: self.optimizer.run_full_optimization(), self.full_opt_btn)
    
    def _run_quick_clean(self):
        def task():
            self._log("> Executing QUICK_CLEAN...")
            self.optimizer.clean_temp_files()
            self.optimizer.clean_browser_cache()
            self.optimizer.flush_dns_cache()
        self._run_in_thread(task)
    
    def _run_ram_optimization(self):
        self._log("> Executing RAM_OPTIMIZE...")
        self._run_in_thread(lambda: self.optimizer.optimize_ram())
    
    def _run_game_mode(self):
        self._log("> Executing GAME_MODE activation...")
        self._run_in_thread(lambda: self.optimizer.enable_game_mode())
    
    def _run_network_optimization(self):
        self._log("> Executing NETWORK_OPTIMIZE...")
        self._run_in_thread(lambda: self.optimizer.optimize_network_gaming())
    
    def _run_power_optimization(self):
        self._log("> Executing HIGH_PERFORMANCE mode...")
        self._run_in_thread(lambda: self.optimizer.optimize_power_plan())
    
    def _run_browser_cache_clean(self):
        self._log("> Executing BROWSER_CACHE cleanup...")
        self._run_in_thread(lambda: self.optimizer.clean_browser_cache())
    
    def _run_windows_update_clean(self):
        self._log("> Executing WINDOWS_UPDATE cache cleanup...")
        self._run_in_thread(lambda: self.optimizer.clean_windows_update_cache())
    
    def _run_dns_optimization(self):
        self._log("> Executing DNS_OPTIMIZE (Cloudflare)...")
        self._run_in_thread(lambda: self.optimizer.optimize_dns())
    
    def _run_services_optimization(self):
        self._log("> Executing SERVICE_KILLER...")
        self._run_in_thread(lambda: self.optimizer.disable_unnecessary_services())
    
    def _run_visual_optimization(self):
        self._log("> Executing VISUAL_FX termination...")
        self._run_in_thread(lambda: self.optimizer.optimize_visual_effects())
    
    def _run_flush_dns(self):
        self._log("> Executing DNS_FLUSH...")
        self._run_in_thread(lambda: self.optimizer.flush_dns_cache())
    
    def _run_disable_xbox(self):
        result = messagebox.askyesno(
            "⚠ CRITICAL WARNING",
            "XBOX SERVICES TERMINATION\n\n"
            "The following will be DISABLED:\n"
            "• Xbox Game Pass\n"
            "• Xbox Application\n"
            "• Cloud Saves\n"
            "• Achievements\n\n"
            "You can restore them anytime.\n\n"
            "PROCEED?"
        )
        if result:
            self._log("> Executing XBOX_TERMINATE...")
            self._run_in_thread(lambda: self.optimizer.disable_xbox_services())
    
    def _run_enable_xbox(self):
        self._log("> Executing XBOX_RESTORE...")
        self._run_in_thread(lambda: self.optimizer.enable_xbox_services())
    
    def _run_restore_visual(self):
        self._log("> Executing VISUAL_FX restoration...")
        self._run_in_thread(lambda: self.optimizer.restore_visual_effects())
    
    def _run_restore_power(self):
        self._log("> Executing BALANCED_POWER mode...")
        self._run_in_thread(lambda: self.optimizer.restore_power_plan())
    
    def _run_ultimate_optimization(self):
        self._log("> Executing ULTIMATE_OPTIMIZATION protocol...")
        self._run_in_thread(lambda: self.optimizer.run_ultimate_optimization())
    
    def _run_input_lag(self):
        self._log("> Executing INPUT_LAG optimization...")
        self._run_in_thread(lambda: self.optimizer.optimize_input_lag())
    
    def _run_mouse_optimization(self):
        self._log("> Executing MOUSE_RAW optimization...")
        self._run_in_thread(lambda: self.optimizer.optimize_mouse())
    
    def _run_fullscreen_fix(self):
        self._log("> Executing FULLSCREEN_FIX...")
        self._run_in_thread(lambda: self.optimizer.disable_fullscreen_optimizations())
    
    def _run_disable_hpet(self):
        result = messagebox.askyesno(
            "⚠ HPET DISABLE",
            "Отключение HPET может снизить input lag.\n\n"
            "⚠️ ТРЕБУЕТСЯ ПЕРЕЗАГРУЗКА!\n\n"
            "Если игры станут работать хуже - включи обратно.\n\n"
            "Продолжить?"
        )
        if result:
            self._log("> Executing HPET_DISABLE...")
            self._run_in_thread(lambda: self.optimizer.disable_hpet())
    
    def _run_gpu_scheduling(self):
        self._log("> Executing GPU_SCHEDULING optimization...")
        self._run_in_thread(lambda: self.optimizer.optimize_gpu_scheduling())
    
    def _run_core_unpark(self):
        self._log("> Executing CORE_UNPARK...")
        self._run_in_thread(lambda: self.optimizer.disable_core_parking())
    
    def _run_disable_bg_apps(self):
        self._log("> Executing BACKGROUND_APPS kill...")
        self._run_in_thread(lambda: self.optimizer.disable_background_apps())
    
    def _run_gpu_vram_clean(self):
        self._log("> Executing GPU_VRAM cleanup...")
        self._run_in_thread(lambda: self.optimizer.clear_gpu_vram())
    
    def _run_disable_tasks(self):
        self._log("> Executing TASK_SCHEDULER optimization...")
        self._run_in_thread(lambda: self.optimizer.disable_scheduled_tasks())
    
    def _run_cpu_affinity(self):
        self._log("> Executing CPU_AFFINITY optimization...")
        self._run_in_thread(lambda: self.optimizer.set_cpu_affinity())
    
    def _run_disable_prefetch(self):
        self._log("> Executing PREFETCH/SUPERFETCH disable...")
        self._run_in_thread(lambda: self.optimizer.optimize_prefetch(enable=False))
    
    def _run_trim(self):
        self._log("> Executing SSD TRIM optimization...")
        self._run_in_thread(lambda: self.optimizer.run_trim())
    
    def _run_benchmark(self):
        self._log("> Executing BENCHMARK...")
        self._run_in_thread(lambda: self.optimizer.run_benchmark_comparison())
    
    def _run_rollback(self):
        result = messagebox.askyesno(
            "⚠ ОТКАТ ИЗМЕНЕНИЙ",
            "Это действие отменит ВСЕ оптимизации:\n\n"
            "• Восстановит службы Windows\n"
            "• Включит Prefetch/Superfetch\n"
            "• Восстановит план питания\n"
            "• Восстановит визуальные эффекты\n"
            "• Включит задачи планировщика\n"
            "• Включит фоновые приложения\n\n"
            "⚠️ ПОТРЕБУЕТСЯ ПЕРЕЗАГРУЗКА!\n\n"
            "Продолжить?"
        )
        if result:
            self._log("> Executing ROLLBACK...")
            self._run_in_thread(lambda: self.optimizer.rollback_all())
    
    def _open_logs(self):
        log_path = self.optimizer.get_log_file_path()
        if log_path and os.path.exists(log_path):
            self._log(f"> Opening logs: {log_path}")
            os.startfile(os.path.dirname(log_path))
        else:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            if os.path.exists(log_dir):
                os.startfile(log_dir)
            else:
                self._log("> Logs folder not found")
    
    def _check_updates(self):
        self._log("> Checking for updates...")
        
        def check_task():
            result = self.updater.check_for_updates()
            
            if result.get("error"):
                self.after(0, lambda: messagebox.showerror(
                    "Ошибка",
                    f"Не удалось проверить обновления:\n{result['error']}"
                ))
                return
            
            if result.get("update_available"):
                self.after(0, lambda: self._prompt_update(result))
            else:
                self.after(0, lambda: messagebox.showinfo(
                    "Обновления",
                    f"У вас последняя версия: v{result['current_version']}"
                ))
        
        self._run_in_thread(check_task, self.update_btn)
    
    def _prompt_update(self, result):
        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Доступна новая версия!\n\n"
            f"Текущая: v{result['current_version']}\n"
            f"Новая: v{result['latest_version']}\n\n"
            f"Скачать и установить?"
        )
        
        if answer:
            self._download_and_install_update()
    
    def _download_and_install_update(self):
        self._log("> Downloading update...")
        
        def update_task():
            def progress_callback(percent):
                self.after(0, lambda p=percent: self.status_label.configure(
                    text=f"[{'▓' * (p//10)}{'░' * (10-p//10)}] {p}%",
                    text_color=NEON_CYAN
                ))
            
            zip_path = self.updater.download_update(progress_callback)
            
            if zip_path:
                success = self.updater.apply_update(zip_path)
                if success:
                    self.after(0, lambda: self._show_restart_dialog())
                else:
                    self.after(0, lambda: messagebox.showerror(
                        "Ошибка",
                        "Не удалось установить обновление"
                    ))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Ошибка",
                    "Не удалось загрузить обновление"
                ))
        
        self._run_in_thread(update_task, self.update_btn)
    
    def _show_restart_dialog(self):
        answer = messagebox.askyesno(
            "Обновление установлено",
            "Обновление успешно установлено!\n\n"
            "Перезапустить приложение сейчас?"
        )
        
        if answer:
            self._restart_app()
    
    def _restart_app(self):
        self._log("> Restarting application...")
        python = sys.executable
        os.execl(python, python, *sys.argv)


if __name__ == "__main__":
    app = OptimizerApp()
    app.mainloop()
