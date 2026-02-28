#!/usr/bin/env python3
"""
KeepAwake Pro — Sleep Prevention Utility
Prevents system sleep via configurable keypress or mouse actions.
Supports Smart AFK simulation, scheduled hours, global hotkeys, and system tray.
"""

import sys
import os
import threading
import time
import json
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# Hide console window on Windows
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.FreeConsole()
    except:
        pass

# Setup logging
import logging
def setup_logging():
    log_dir = Path.home() / ".keepawake_pro" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"keepawake_pro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,  # Reduced logging level for performance
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8')
        ],
        force=True
    )

    return logging.getLogger('KeepAwakePro')

logger = setup_logging()
logger.info("=== KeepAwake Pro Starting ===")

# Import GUI frameworks
try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    import customtkinter as ctk
    logger.info("CustomTkinter imported successfully")

    # Set appearance mode early
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    GUI_AVAILABLE = True

except ImportError as e:
    logger.error(f"GUI import failed: {e}")
    print(f"Error: GUI libraries not available: {e}")
    print("Please install: pip install customtkinter")
    sys.exit(1)

# Import other features
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
    logger.info("System tray available")
except ImportError:
    TRAY_AVAILABLE = False
    logger.warning("System tray not available")

try:
    from pynput import keyboard
    from pynput.keyboard import Key, Controller as KeyboardController
    INPUT_AVAILABLE = True
    logger.info("Input control available")
except ImportError:
    INPUT_AVAILABLE = False
    logger.warning("Input control not available")

try:
    import psutil
    MONITORING_AVAILABLE = True
    logger.info("Performance monitoring available")
except ImportError:
    MONITORING_AVAILABLE = False
    logger.warning("Performance monitoring not available")


class SmartAFKManager:
    """
    Smart AFK simulation - Makes you appear offline periodically like a normal user

    HOW IT WORKS:
    1. Monitors your prevention actions
    2. After 5 minutes of steady actions, may trigger AFK simulation
    3. During AFK simulation (30-180 seconds), no prevention actions are sent
    4. This makes you appear "offline" or "away" briefly
    5. Resumes normal prevention after AFK period

    BENEFITS:
    - Prevents appearing "always online" 24/7
    - Simulates natural computer usage patterns
    - Useful for games, monitoring software, work applications
    - Random timing prevents detection patterns
    """

    def __init__(self, app_instance):
        self.app = app_instance
        self.enabled = False
        self.last_action_time = time.time()
        self.afk_active = False
        self.worker_thread = None
        self.running = False
        self._stop_event = threading.Event()

        # AFK settings — loaded from app config so user can customise them
        cfg = app_instance.config
        self.check_interval = 60
        self.inactivity_threshold = 300
        self.afk_min_duration = cfg.get("afk_min_duration", 30)
        self.afk_max_duration = cfg.get("afk_max_duration", 120)
        self.afk_probability = cfg.get("afk_probability", 0.25)

        logger.info("Smart AFK Manager initialized")
        logger.info(f"AFK Logic: After {self.inactivity_threshold}s of actions, {self.afk_probability*100}% chance of {self.afk_min_duration}-{self.afk_max_duration}s AFK simulation")

    def start(self):
        """Start smart AFK monitoring"""
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self._stop_event.clear()
        self.enabled = True
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info("Smart AFK monitoring started")

    def stop(self):
        """Stop smart AFK monitoring"""
        self.enabled = False
        self.running = False
        self._stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Smart AFK monitoring stopped")

    def register_action(self):
        """Register a prevention action (called by main app)"""
        self.last_action_time = time.time()

    def is_afk_active(self):
        """Check if AFK simulation is currently active"""
        return self.afk_active

    def get_smart_interval(self, base_interval):
        """Get interval with smart randomization"""
        if not self.enabled:
            return base_interval

        if self.afk_active:
            # During AFK, use longer intervals (simulating being away)
            return base_interval + random.randint(30, 90)
        else:
            # Normal operation with slight variation (simulating human timing)
            return base_interval + random.randint(-10, 20)

    def get_status_text(self):
        """Get current AFK status for display"""
        if not self.enabled:
            return "Smart AFK: Disabled"
        elif self.afk_active:
            return "Smart AFK: 🟠 Simulating AFK"
        else:
            return "Smart AFK: 🟢 Active"

    def _worker(self):
        """Smart AFK worker thread"""
        logger.info("Smart AFK worker started")

        while self.running and not self._stop_event.is_set():
            try:
                if not self.enabled:
                    self._stop_event.wait(timeout=self.check_interval)
                    continue

                current_time = time.time()
                time_since_action = current_time - self.last_action_time

                # Check if we should trigger AFK simulation
                if (time_since_action > self.inactivity_threshold and
                    not self.afk_active and
                    random.random() < self.afk_probability):

                    # Start AFK simulation
                    afk_duration = random.randint(self.afk_min_duration, self.afk_max_duration)
                    self.afk_active = True
                    logger.info(f"Starting AFK simulation for {afk_duration} seconds (simulating user being away)")

                    # Interruptible sleep: wakes immediately on stop signal
                    self._stop_event.wait(timeout=afk_duration)

                    # End AFK simulation
                    self.afk_active = False
                    self.last_action_time = time.time()
                    if not self._stop_event.is_set():
                        logger.info("AFK simulation ended - resuming normal prevention")

                if not self._stop_event.is_set():
                    self._stop_event.wait(timeout=self.check_interval)

            except Exception as e:
                logger.error(f"Smart AFK worker error: {e}")
                self._stop_event.wait(timeout=30)

        logger.info("Smart AFK worker stopped")


class SimpleThemeManager:
    """Simple but reliable theme management with fixed switching"""

    def __init__(self):
        self.current_theme = "dark"
        self._lock = threading.Lock()
        logger.info("Theme manager initialized")

    def get_colors(self, theme=None):
        """Get color scheme - simplified but working"""
        with self._lock:
            if theme is None:
                theme = self.current_theme

            if theme == "light":
                return {
                    'bg': "#f0f2f5",          # light blue-grey page bg
                    'sidebar_bg': "#e3e6eb",  # slightly darker sidebar
                    'card_bg': "#ffffff",      # white cards stand out from bg
                    'text': "#1a1a1a",
                    'text_secondary': "#4a4a4a",
                    'text_muted': "#7a7a7a",
                    'accent': "#0078d4",
                    'success': "#107c10",
                    'danger': "#c7350a",
                    'border': "#c0c4cc",
                    'hover': "#d8dce3",
                    'button_bg': "#e8eaed",
                    'running_bg': "#d4edda",
                    'running_text': "#155724",
                    'stopped_bg': "#e8eaed",
                    'stopped_text': "#5a5a5a",
                    'selected_bg': "#0078d4",
                    'selected_text': "#ffffff",
                    'selected_hover': "#0078d4",
                }
            else:
                return {
                    # Dark theme colors  
                    'bg': "#1e1e1e",
                    'sidebar_bg': "#252526",
                    'card_bg': "#2d2d30",
                    'text': "#ffffff",
                    'text_secondary': "#cccccc",
                    'text_muted': "#969696",
                    'accent': "#0e639c",
                    'success': "#14a085",
                    'danger': "#f85149",
                    'border': "#3e3e42",
                    'hover': "#2a2d2e",
                    'button_bg': "#0e1419",
                    'running_bg': "#1a4f1a",
                    'running_text': "#14a085",
                    'stopped_bg': "#2d2d30",
                    'stopped_text': "#969696",
                    # FIXED: Selected tab colors for dark mode
                    'selected_bg': "#0e639c",
                    'selected_text': "#ffffff", 
                    'selected_hover': "#0e639c"  # Same as selected to prevent color change
                }

    def set_theme(self, theme):
        """Set theme with proper locking"""
        with self._lock:
            self.current_theme = theme
            logger.info(f"Theme set to: {theme}")

    def toggle_theme(self):
        """Toggle between themes"""
        with self._lock:
            new_theme = "light" if self.current_theme == "dark" else "dark"
            self.current_theme = new_theme
            return new_theme


class RobustSidebar:
    """Robust sidebar with FIXED hover behavior for selected tabs"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.current_tab = "dashboard"
        self.nav_buttons = {}
        self.status_button = None

        try:
            self.create_sidebar()
            logger.info("Sidebar created successfully")
        except Exception as e:
            logger.error(f"Sidebar creation failed: {e}")
            raise

    def create_sidebar(self):
        """Create sidebar with fixed hover behavior"""
        colors = self.app.theme_manager.get_colors()

        # Create sidebar container
        self.sidebar_frame = ctk.CTkFrame(
            self.parent,
            width=180,
            corner_radius=0,
            fg_color=colors['sidebar_bg']
        )
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # App title
        try:
            title_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=60)
            title_frame.pack(fill="x", padx=10, pady=(10, 5))
            title_frame.pack_propagate(False)

            title_label = ctk.CTkLabel(
                title_frame,
                text="🛡️ KeepAwake Pro",
                font=("Segoe UI", 14, "bold"),
                text_color=colors['text']
            )
            title_label.pack(pady=(10, 0))

            version_label = ctk.CTkLabel(
                title_frame,
                text="Sleep Prevention",
                font=("Segoe UI", 8),
                text_color=colors['text_muted']
            )
            version_label.pack()

        except Exception as e:
            logger.error(f"Title creation error: {e}")

        # Navigation buttons
        try:
            nav_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
            nav_frame.pack(fill="both", expand=True, padx=8, pady=5)

            nav_items = [
                ("dashboard", "📊 Dashboard"),
                ("settings", "⚙️ Settings"),
                ("hotkeys", "⌨️ Hotkeys"),
                ("performance", "📈 Performance"),
                ("about", "ℹ️ About")
            ]

            for tab_id, title in nav_items:
                try:
                    btn = ctk.CTkButton(
                        nav_frame,
                        text=title,
                        font=("Segoe UI", 10),
                        height=30,
                        anchor="w",
                        command=lambda t=tab_id: self.safe_switch_tab(t),
                        fg_color="transparent",
                        text_color=colors['text_secondary'],
                        hover_color=colors['hover']
                    )
                    btn.pack(fill="x", pady=1)
                    self.nav_buttons[tab_id] = btn

                except Exception as e:
                    logger.error(f"Navigation button creation error for {tab_id}: {e}")

        except Exception as e:
            logger.error(f"Navigation creation error: {e}")

        # Status button
        try:
            status_frame = ctk.CTkFrame(
                self.sidebar_frame,
                fg_color=colors['card_bg'],
                corner_radius=8,
                border_width=1,
                border_color=colors['border']
            )
            status_frame.pack(fill="x", padx=8, pady=(5, 10), side="bottom")

            self.status_button = ctk.CTkButton(
                status_frame,
                text="⏸️",
                font=("Segoe UI", 18),
                height=40,
                width=40,
                command=self.safe_toggle_prevention,
                fg_color=colors['stopped_bg'],
                text_color=colors['stopped_text'],
                hover_color=colors['hover']
            )
            self.status_button.pack(pady=8)

        except Exception as e:
            logger.error(f"Status button creation error: {e}")

        # Set initial tab
        self.switch_tab("dashboard")

    def safe_switch_tab(self, tab_id):
        """Safe tab switching with error handling"""
        try:
            self.switch_tab(tab_id)
        except Exception as e:
            logger.error(f"Safe tab switch error: {e}")

    def safe_toggle_prevention(self):
        """Safe prevention toggle with error handling"""
        try:
            if hasattr(self.app, 'toggle_prevention'):
                self.app.toggle_prevention()
        except Exception as e:
            logger.error(f"Safe prevention toggle error: {e}")

    def switch_tab(self, tab_id):
        """Switch tab with FIXED hover behavior"""
        try:
            colors = self.app.theme_manager.get_colors()

            for btn_id, btn in self.nav_buttons.items():
                if btn_id == tab_id:
                    # FIXED: Selected tab with no hover color change
                    btn.configure(
                        fg_color=colors['selected_bg'],
                        text_color=colors['selected_text'],
                        font=("Segoe UI", 10, "bold"),
                        hover_color=colors['selected_hover']  # Same as selected color
                    )
                else:
                    btn.configure(
                        fg_color="transparent",
                        text_color=colors['text_secondary'],
                        font=("Segoe UI", 10, "normal"),
                        hover_color=colors['hover']  # Normal hover for unselected
                    )

            self.current_tab = tab_id

            # Notify app to switch content
            if hasattr(self.app, 'switch_content'):
                self.app.switch_content(tab_id)

        except Exception as e:
            logger.error(f"Tab switch error: {e}")

    def update_status(self, is_running):
        """Update status button"""
        try:
            if not self.status_button:
                return

            colors = self.app.theme_manager.get_colors()

            if is_running:
                self.status_button.configure(
                    text="🔄",
                    fg_color=colors['running_bg'],
                    text_color=colors['running_text']
                )
            else:
                self.status_button.configure(
                    text="⏸️",
                    fg_color=colors['stopped_bg'],
                    text_color=colors['stopped_text']
                )

        except Exception as e:
            logger.error(f"Status update error: {e}")

    def update_theme(self):
        """FIXED: Update sidebar theme without crashing"""
        try:
            colors = self.app.theme_manager.get_colors()

            # Update sidebar background
            if hasattr(self, 'sidebar_frame'):
                self.sidebar_frame.configure(fg_color=colors['sidebar_bg'])

            # Update navigation buttons with proper colors
            for btn_id, btn in self.nav_buttons.items():
                try:
                    if btn_id == self.current_tab:
                        btn.configure(
                            fg_color=colors['selected_bg'],
                            text_color=colors['selected_text'],
                            hover_color=colors['selected_hover']
                        )
                    else:
                        btn.configure(
                            fg_color="transparent",
                            text_color=colors['text_secondary'],
                            hover_color=colors['hover']
                        )
                except Exception as btn_error:
                    logger.error(f"Button theme update error: {btn_error}")

            # Update status button
            self.update_status(self.app.is_running)

        except Exception as e:
            logger.error(f"Sidebar theme update error: {e}")


class RobustContentArea:
    """Robust content area with FIXED theme switching"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.content_frames = {}
        self.current_frame = None

        try:
            self.create_content_area()
            logger.info("Content area created successfully")
        except Exception as e:
            logger.error(f"Content area creation failed: {e}")
            raise

    def create_content_area(self):
        """Create main content container"""
        colors = self.app.theme_manager.get_colors()

        # Main content frame
        self.main_frame = ctk.CTkFrame(
            self.parent,
            corner_radius=0,
            fg_color=colors['bg']
        )
        self.main_frame.pack(side="right", fill="both", expand=True)

        # Create all content frames
        self.create_all_content()

        # Show initial content
        self.show_content("dashboard")

    def create_all_content(self):
        """Create all content frames with error handling"""
        content_creators = [
            ("dashboard", self.create_dashboard),
            ("settings", self.create_settings),
            ("hotkeys", self.create_hotkeys),
            ("performance", self.create_performance),
            ("about", self.create_about)
        ]

        for content_id, creator_func in content_creators:
            try:
                frame = creator_func()
                self.content_frames[content_id] = frame
                logger.info(f"Created {content_id} content successfully")
            except Exception as e:
                logger.error(f"Failed to create {content_id} content: {e}")
                # Create fallback content
                self.content_frames[content_id] = self.create_fallback_content(content_id, str(e))

    def create_fallback_content(self, content_id, error_msg):
        """Create fallback content when creation fails"""
        colors = self.app.theme_manager.get_colors()

        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        error_label = ctk.CTkLabel(
            frame,
            text=f"❌ Error loading {content_id}\n{error_msg}",
            font=("Segoe UI", 12),
            text_color=colors['danger']
        )
        error_label.pack(expand=True)

        return frame

    def create_dashboard(self):
        """Create dashboard content"""
        colors = self.app.theme_manager.get_colors()

        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        # Header
        header = ctk.CTkLabel(
            frame,
            text="📊 Dashboard",
            font=("Segoe UI", 20, "bold"),
            text_color=colors['text']
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # Status section
        status_frame = ctk.CTkFrame(
            frame,
            fg_color=colors['card_bg'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border']
        )
        status_frame.pack(fill="x", padx=20, pady=10)

        # Status content
        status_content = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_content.pack(fill="x", padx=15, pady=15)

        # Status icon
        self.status_icon = ctk.CTkLabel(
            status_content,
            text="⏸️",
            font=("Segoe UI", 24)
        )
        self.status_icon.pack(side="left", padx=(0, 15))

        # Status info
        status_info = ctk.CTkFrame(status_content, fg_color="transparent")
        status_info.pack(side="left", fill="both", expand=True)

        self.status_text = ctk.CTkLabel(
            status_info,
            text="Stopped",
            font=("Segoe UI", 16, "bold"),
            text_color=colors['text'],
            anchor="w"
        )
        self.status_text.pack(fill="x")

        self.stats_text = ctk.CTkLabel(
            status_info,
            text="Actions: 0 | Session: 00:00:00",
            font=("Segoe UI", 10),
            text_color=colors['text_secondary'],
            anchor="w"
        )
        self.stats_text.pack(fill="x")

        # NEW: AFK Status display
        self.afk_status_text = ctk.CTkLabel(
            status_info,
            text="Smart AFK: Disabled",
            font=("Segoe UI", 9),
            text_color=colors['text_muted'],
            anchor="w"
        )
        self.afk_status_text.pack(fill="x")

        # Control buttons (stacked vertically on the right)
        btn_frame = ctk.CTkFrame(status_content, fg_color="transparent")
        btn_frame.pack(side="right")

        self.main_button = ctk.CTkButton(
            btn_frame,
            text="▶ START",
            font=("Segoe UI", 11, "bold"),
            height=32,
            width=110,
            command=self.app.on_main_button_click,
            fg_color=colors['success']
        )
        self.main_button.pack(side="top")

        self.stop_button = ctk.CTkButton(
            btn_frame,
            text="⏹ STOP",
            font=("Segoe UI", 10),
            height=28,
            width=110,
            command=self.app.stop_prevention,
            fg_color=colors['danger']
        )
        # Hidden until prevention is running — shown via update_dashboard

        # Simple metrics
        metrics_frame = ctk.CTkFrame(
            frame,
            fg_color=colors['card_bg'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border']
        )
        metrics_frame.pack(fill="x", padx=20, pady=10)

        metrics_title = ctk.CTkLabel(
            metrics_frame,
            text="📊 Metrics",
            font=("Segoe UI", 14, "bold"),
            text_color=colors['text']
        )
        metrics_title.pack(padx=15, pady=(15, 10), anchor="w")

        # Metrics content
        metrics_content = ctk.CTkFrame(metrics_frame, fg_color="transparent")
        metrics_content.pack(fill="x", padx=15, pady=(0, 15))

        self.cpu_label = ctk.CTkLabel(
            metrics_content,
            text="CPU: 0.0%",
            font=("Segoe UI", 10),
            text_color=colors['text_secondary']
        )
        self.cpu_label.pack(side="left", padx=(0, 20))

        self.memory_label = ctk.CTkLabel(
            metrics_content,
            text="RAM: 0 MB",
            font=("Segoe UI", 10),
            text_color=colors['text_secondary']
        )
        self.memory_label.pack(side="left", padx=(0, 20))

        self.uptime_label = ctk.CTkLabel(
            metrics_content,
            text="Uptime: 00:00:00",
            font=("Segoe UI", 10),
            text_color=colors['text_secondary']
        )
        self.uptime_label.pack(side="left")

        return frame

    def create_settings(self):
        """Create settings content with AFK explanation"""
        colors = self.app.theme_manager.get_colors()

        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        # Header
        header = ctk.CTkLabel(
            frame,
            text="⚙️ Settings",
            font=("Segoe UI", 20, "bold"),
            text_color=colors['text']
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # Settings container
        settings_container = ctk.CTkScrollableFrame(
            frame,
            fg_color=colors['card_bg'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border']
        )
        settings_container.pack(fill="both", expand=True, padx=20, pady=10)

        # ── Interval ──────────────────────────────────────────────────
        interval_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        interval_frame.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            interval_frame,
            text="⏱️ Prevention Interval (seconds, min 10):",
            font=("Segoe UI", 12, "bold"),
            text_color=colors['text']
        ).pack(anchor="w", pady=(0, 5))

        # Digits-only validator
        vcmd = (interval_frame.register(lambda s: s == "" or s.isdigit()), '%P')
        self.interval_entry = ctk.CTkEntry(
            interval_frame,
            font=("Segoe UI", 11),
            height=30,
            validate='key',
            validatecommand=vcmd
        )
        self.interval_entry.pack(fill="x", pady=(0, 5))
        self.interval_entry.insert(0, str(self.app.config.get("interval", 59)))

        # ── Auto-start ────────────────────────────────────────────────
        self.autostart_var = ctk.BooleanVar(value=self.app.config.get("auto_start", False))
        ctk.CTkCheckBox(
            settings_container,
            text="🚀 Auto-start prevention when app opens",
            font=("Segoe UI", 11),
            variable=self.autostart_var
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # ── Prevention Method ──────────────────────────────────────────
        method_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        method_frame.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            method_frame,
            text="🎯 Prevention Method:",
            font=("Segoe UI", 12, "bold"),
            text_color=colors['text']
        ).pack(anchor="w", pady=(0, 5))

        method_options = ["f15", "f16", "scroll_lock", "mouse_move"]
        method_labels = {
            "f15": "F15 key (default — invisible, safe)",
            "f16": "F16 key (alternative function key)",
            "scroll_lock": "Scroll Lock key",
            "mouse_move": "Mouse nudge (1px right then back)",
        }
        current_method = self.app.config.get("prevention_method", "f15")
        self.method_var = ctk.StringVar(value=method_labels.get(current_method, method_labels["f15"]))

        self.method_dropdown = ctk.CTkOptionMenu(
            method_frame,
            values=list(method_labels.values()),
            variable=self.method_var,
            font=("Segoe UI", 10),
            height=30
        )
        self.method_dropdown.pack(fill="x")
        # Map display label → config key
        self._method_label_to_key = {v: k for k, v in method_labels.items()}

        # ── Smart AFK ─────────────────────────────────────────────────
        afk_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        afk_frame.pack(fill="x", padx=15, pady=(10, 5))

        self.smart_afk_var = ctk.BooleanVar(value=self.app.config.get("smart_afk", False))
        ctk.CTkCheckBox(
            afk_frame,
            text="🤖 Smart AFK Simulation",
            font=("Segoe UI", 11, "bold"),
            variable=self.smart_afk_var
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(
            afk_frame,
            text="Periodically pauses prevention to simulate natural away periods.",
            font=("Segoe UI", 9),
            text_color=colors['text_muted'],
            anchor="w"
        ).pack(anchor="w")

        # AFK sliders
        afk_sliders_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        afk_sliders_frame.pack(fill="x", padx=15, pady=(5, 5))

        def make_slider_row(parent, label, from_, to, step, config_key, fmt="{:.0f}", init_val=None):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 10),
                         text_color=colors['text_secondary'], width=160, anchor="w").pack(side="left")
            current = init_val if init_val is not None else self.app.config.get(config_key, from_)
            display = ctk.CTkLabel(row, text=fmt.format(current),
                                    font=("Segoe UI", 10, "bold"), text_color=colors['accent'], width=45)
            display.pack(side="right")
            def on_change(v, d=display, f=fmt):
                d.configure(text=f.format(float(v)))
            slider = ctk.CTkSlider(row, from_=from_, to=to, number_of_steps=int((to - from_) / step),
                                    command=on_change)
            slider.set(current)
            slider.pack(side="left", fill="x", expand=True, padx=(5, 5))
            return slider

        # Probability slider uses percentage (5-75), but config stores decimal (0.0-1.0)
        prob_pct = round(self.app.config.get("afk_probability", 0.25) * 100)
        self.afk_prob_slider = make_slider_row(
            afk_sliders_frame, "Trigger chance:", 5, 75, 5, "afk_probability", "{:.0f}%", init_val=prob_pct)
        self.afk_min_slider  = make_slider_row(
            afk_sliders_frame, "AFK min duration (s):", 10, 120, 5, "afk_min_duration")
        self.afk_max_slider  = make_slider_row(
            afk_sliders_frame, "AFK max duration (s):", 30, 300, 10, "afk_max_duration")

        # Store raw sliders get methods need %-to-decimal conversion for probability
        # (handled in apply_settings)

        # ── Schedule ──────────────────────────────────────────────────
        sched_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        sched_frame.pack(fill="x", padx=15, pady=(10, 5))

        self.schedule_var = ctk.BooleanVar(value=self.app.config.get("schedule_enabled", False))
        ctk.CTkCheckBox(
            sched_frame,
            text="🕐 Only run during scheduled hours (HH:MM, 24h format)",
            font=("Segoe UI", 11, "bold"),
            variable=self.schedule_var
        ).pack(anchor="w", pady=(0, 5))

        sched_times = ctk.CTkFrame(sched_frame, fg_color="transparent")
        sched_times.pack(fill="x")

        ctk.CTkLabel(sched_times, text="From:", font=("Segoe UI", 10),
                     text_color=colors['text_secondary']).pack(side="left")
        self.sched_start_entry = ctk.CTkEntry(sched_times, width=60, font=("Segoe UI", 10), height=28)
        self.sched_start_entry.insert(0, self.app.config.get("schedule_start", "09:00"))
        self.sched_start_entry.pack(side="left", padx=(5, 15))

        ctk.CTkLabel(sched_times, text="To:", font=("Segoe UI", 10),
                     text_color=colors['text_secondary']).pack(side="left")
        self.sched_end_entry = ctk.CTkEntry(sched_times, width=60, font=("Segoe UI", 10), height=28)
        self.sched_end_entry.insert(0, self.app.config.get("schedule_end", "17:00"))
        self.sched_end_entry.pack(side="left", padx=(5, 0))

        # ── Theme ─────────────────────────────────────────────────────
        theme_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        theme_frame.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            theme_frame,
            text="🎨 Theme:",
            font=("Segoe UI", 12, "bold"),
            text_color=colors['text']
        ).pack(side="left", padx=(0, 10))

        self.theme_button = ctk.CTkButton(
            theme_frame,
            text=f"Switch to {'Light' if self.app.theme_manager.current_theme == 'dark' else 'Dark'} Mode",
            command=self.app.toggle_theme,
            height=30,
            width=150
        )
        self.theme_button.pack(side="left")

        # ── Action buttons ────────────────────────────────────────────
        button_frame = ctk.CTkFrame(settings_container, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            button_frame,
            text="Apply Settings",
            command=self.apply_settings,
            height=35,
            width=130,
            fg_color=colors['success']
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            button_frame,
            text="Close App",
            command=self.app.quit_completely,
            height=35,
            width=100,
            fg_color=colors['danger']
        ).pack(side="right")

        return frame

    def create_hotkeys(self):
        """Create hotkeys content"""
        colors = self.app.theme_manager.get_colors()

        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        # Header
        header = ctk.CTkLabel(
            frame,
            text="⌨️ Hotkeys",
            font=("Segoe UI", 20, "bold"),
            text_color=colors['text']
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # Hotkeys info
        info_frame = ctk.CTkFrame(
            frame,
            fg_color=colors['card_bg'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border']
        )
        info_frame.pack(fill="both", expand=True, padx=20, pady=10)

        hotkeys_text = f"""⌨️ GLOBAL HOTKEYS:

🎯 Toggle Prevention: {self.app.config['hotkeys']['toggle']}
   Start or stop sleep prevention from anywhere

👁️ Hide/Show Window: {self.app.config['hotkeys']['hide_show']}
   Toggle application window visibility

💡 USAGE:
• Hotkeys work even when the app is minimized
• Use Ctrl+Alt+K for quick prevention control
• Use Ctrl+Alt+H to hide/show the window
• Hotkeys are system-wide and always active"""

        info_textbox = ctk.CTkTextbox(
            info_frame,
            font=("Segoe UI", 11),
            wrap="word",
            fg_color=colors['card_bg'],
            text_color=colors['text']
        )
        info_textbox.pack(fill="both", expand=True, padx=15, pady=15)
        info_textbox.insert("0.0", hotkeys_text)
        info_textbox.configure(state="disabled")

        return frame

    def create_performance(self):
        """Create performance content"""
        colors = self.app.theme_manager.get_colors()

        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        # Header
        header = ctk.CTkLabel(
            frame,
            text="📈 Performance",
            font=("Segoe UI", 20, "bold"),
            text_color=colors['text']
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # Performance info
        perf_frame = ctk.CTkFrame(
            frame,
            fg_color=colors['card_bg'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border']
        )
        perf_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Real-time metrics
        metrics_title = ctk.CTkLabel(
            perf_frame,
            text="📊 Real-time Metrics",
            font=("Segoe UI", 14, "bold"),
            text_color=colors['text']
        )
        metrics_title.pack(padx=15, pady=(15, 10), anchor="w")

        metrics_content = ctk.CTkFrame(perf_frame, fg_color="transparent")
        metrics_content.pack(fill="x", padx=15, pady=(0, 15))

        self.perf_cpu_label = ctk.CTkLabel(
            metrics_content,
            text="🖥️ CPU: 0.0%",
            font=("Segoe UI", 12),
            text_color=colors['text_secondary']
        )
        self.perf_cpu_label.pack(anchor="w", pady=2)

        self.perf_memory_label = ctk.CTkLabel(
            metrics_content,
            text="💾 Memory: 0 MB",
            font=("Segoe UI", 12),
            text_color=colors['text_secondary']
        )
        self.perf_memory_label.pack(anchor="w", pady=2)

        self.perf_uptime_label = ctk.CTkLabel(
            metrics_content,
            text="⏰ Uptime: 00:00:00",
            font=("Segoe UI", 12),
            text_color=colors['text_secondary']
        )
        self.perf_uptime_label.pack(anchor="w", pady=2)

        # Session stats
        stats_title = ctk.CTkLabel(
            perf_frame,
            text="📊 Session Statistics",
            font=("Segoe UI", 14, "bold"),
            text_color=colors['text']
        )
        stats_title.pack(padx=15, pady=(15, 10), anchor="w")

        self.stats_textbox = ctk.CTkTextbox(
            perf_frame,
            height=200,
            font=("Consolas", 9),
            fg_color=colors['card_bg'],
            text_color=colors['text']
        )
        self.stats_textbox.pack(fill="x", padx=15, pady=(0, 15))

        return frame

    def create_about(self):
        """Create about content"""
        colors = self.app.theme_manager.get_colors()

        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        # Header
        header = ctk.CTkLabel(
            frame,
            text="ℹ️ About",
            font=("Segoe UI", 20, "bold"),
            text_color=colors['text']
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # About info
        about_frame = ctk.CTkFrame(
            frame,
            fg_color=colors['card_bg'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border']
        )
        about_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # App icon and title
        title_frame = ctk.CTkFrame(about_frame, fg_color="transparent")
        title_frame.pack(pady=20)

        icon_label = ctk.CTkLabel(
            title_frame,
            text="🛡️",
            font=("Segoe UI", 40)
        )
        icon_label.pack()

        app_title = ctk.CTkLabel(
            title_frame,
            text="KeepAwake Pro",
            font=("Segoe UI", 24, "bold"),
            text_color=colors['text']
        )
        app_title.pack(pady=(10, 0))

        version_label = ctk.CTkLabel(
            title_frame,
            text="Sleep Prevention Utility",
            font=("Segoe UI", 12),
            text_color=colors['text_muted']
        )
        version_label.pack()

        # System info
        info_text = f"""SYSTEM
  Platform:  {sys.platform}
  Python:    {sys.version.split()[0]}
  Data dir:  {str(Path.home() / ".keepawake_pro")}

FEATURES
  • Configurable prevention method (F15, F16, Scroll Lock, Mouse nudge)
  • Smart AFK simulation — appears naturally away at random intervals
  • Scheduled hours — only runs during specified time window
  • Pause / Resume without ending a session
  • Global hotkeys  (Ctrl+Alt+K  /  Ctrl+Alt+H)
  • System tray — minimize, restore, or quit from tray
  • Session statistics stored locally
  • Light and dark theme

SMART AFK
  Periodically pauses prevention to simulate natural away periods.
  Trigger chance, min and max duration are fully adjustable in Settings.

HOTKEYS
  Ctrl+Alt+K   Toggle prevention on / off
  Ctrl+Alt+H   Hide / show the window

PRIVACY
  No network connections or telemetry.
  All settings and history stored in ~/.keepawake_pro/"""

        info_textbox = ctk.CTkTextbox(
            about_frame,
            font=("Segoe UI", 10),
            wrap="word",
            fg_color=colors['card_bg'],
            text_color=colors['text']
        )
        info_textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        info_textbox.insert("0.0", info_text)
        info_textbox.configure(state="disabled")

        return frame

    def show_content(self, content_id):
        """Show specific content with error handling"""
        try:
            # Hide current content
            if self.current_frame:
                self.current_frame.pack_forget()

            # Show new content
            if content_id in self.content_frames:
                frame = self.content_frames[content_id]
                frame.pack(fill="both", expand=True)
                self.current_frame = frame
                logger.info(f"Showing {content_id} content")
            else:
                logger.error(f"Content {content_id} not found")

        except Exception as e:
            logger.error(f"Error showing content {content_id}: {e}")

    def apply_settings(self):
        """Apply all settings"""
        try:
            # Interval
            try:
                interval = int(self.interval_entry.get())
                if interval < 10:
                    raise ValueError("Interval must be at least 10 seconds")
                self.app.config["interval"] = interval
            except ValueError as e:
                messagebox.showerror("Settings Error", str(e))
                return

            # Auto-start
            self.app.config["auto_start"] = self.autostart_var.get()

            # Prevention method
            label = self.method_var.get()
            self.app.config["prevention_method"] = self._method_label_to_key.get(label, "f15")

            # Smart AFK toggle
            self.app.config["smart_afk"] = self.smart_afk_var.get()

            # AFK sliders (probability stored as 0-1 decimal, slider is 5-75%)
            self.app.config["afk_probability"] = round(self.afk_prob_slider.get() / 100, 2)
            afk_min = int(self.afk_min_slider.get())
            afk_max = int(self.afk_max_slider.get())
            if afk_min >= afk_max:
                messagebox.showerror("Settings Error", "AFK min duration must be less than max duration.")
                return
            self.app.config["afk_min_duration"] = afk_min
            self.app.config["afk_max_duration"] = afk_max

            # Push AFK params live into the running manager
            mgr = self.app.smart_afk_manager
            mgr.afk_probability = self.app.config["afk_probability"]
            mgr.afk_min_duration = afk_min
            mgr.afk_max_duration = afk_max

            if self.app.config["smart_afk"]:
                mgr.start()
            else:
                mgr.stop()

            # Schedule
            import re
            time_re = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
            sched_start = self.sched_start_entry.get().strip()
            sched_end   = self.sched_end_entry.get().strip()
            if self.schedule_var.get():
                if not time_re.match(sched_start) or not time_re.match(sched_end):
                    messagebox.showerror("Settings Error", "Schedule times must be in HH:MM format (24h).")
                    return
                if sched_start >= sched_end:
                    messagebox.showerror("Settings Error", "Schedule start must be earlier than end time.")
                    return
            self.app.config["schedule_enabled"] = self.schedule_var.get()
            self.app.config["schedule_start"]   = sched_start
            self.app.config["schedule_end"]     = sched_end

            self.app.save_config()
            messagebox.showinfo("Settings", "Settings applied successfully!")

        except Exception as e:
            logger.error(f"Settings apply error: {e}")
            messagebox.showerror("Error", f"Error applying settings: {e}")

    def update_dashboard(self, is_running, is_paused, stats, cpu, memory, uptime):
        """Update dashboard elements for three states: stopped / running / paused"""
        try:
            colors = self.app.theme_manager.get_colors()

            # Determine state strings and colors
            if is_running and is_paused:
                icon, status_label = "⏸️", "Paused"
                main_btn_text = "▶ RESUME"
                main_btn_color = colors['accent']
                show_stop = True
            elif is_running:
                icon, status_label = "🔄", "Running"
                main_btn_text = "⏸ PAUSE"
                main_btn_color = colors['accent']
                show_stop = True
            else:
                icon, status_label = "⏸️", "Stopped"
                main_btn_text = "▶ START"
                main_btn_color = colors['success']
                show_stop = False

            if hasattr(self, 'status_icon'):
                self.status_icon.configure(text=icon)
            if hasattr(self, 'status_text'):
                self.status_text.configure(text=status_label)
            if hasattr(self, 'stats_text'):
                self.stats_text.configure(text=stats)
            if hasattr(self, 'afk_status_text'):
                self.afk_status_text.configure(text=self.app.smart_afk_manager.get_status_text())

            if hasattr(self, 'main_button'):
                self.main_button.configure(text=main_btn_text, fg_color=main_btn_color)

            # Show/hide STOP button
            if hasattr(self, 'stop_button'):
                if show_stop:
                    self.stop_button.pack(side="top", pady=(2, 0))
                else:
                    self.stop_button.pack_forget()

            # Update metrics
            if hasattr(self, 'cpu_label'):
                self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
            if hasattr(self, 'memory_label'):
                self.memory_label.configure(text=f"RAM: {memory:.1f} MB")
            if hasattr(self, 'uptime_label'):
                self.uptime_label.configure(text=f"Uptime: {uptime}")

        except Exception as e:
            logger.error(f"Dashboard update error: {e}")

    def update_performance(self, cpu, memory, uptime, session_stats):
        """Update performance tab"""
        try:
            if hasattr(self, 'perf_cpu_label'):
                self.perf_cpu_label.configure(text=f"🖥️ CPU: {cpu:.1f}%")
            if hasattr(self, 'perf_memory_label'):
                self.perf_memory_label.configure(text=f"💾 Memory: {memory:.1f} MB")
            if hasattr(self, 'perf_uptime_label'):
                self.perf_uptime_label.configure(text=f"⏰ Uptime: {uptime}")

            if hasattr(self, 'stats_textbox'):
                current_text = self.stats_textbox.get("0.0", "end").strip()
                if current_text != session_stats.strip():
                    self.stats_textbox.delete("0.0", "end")
                    self.stats_textbox.insert("0.0", session_stats)
                    self.stats_textbox.see("0.0")

        except Exception as e:
            logger.error(f"Performance update error: {e}")

    def update_theme(self):
        """FIXED: Update content area theme without crashing"""
        try:
            colors = self.app.theme_manager.get_colors()

            # FIXED: Only update colors, don't recreate content frames
            if hasattr(self, 'main_frame'):
                self.main_frame.configure(fg_color=colors['bg'])

            # Update text colors of existing elements
            for content_id, frame in self.content_frames.items():
                try:
                    # Update frame colors
                    frame.configure(fg_color="transparent")
                except:
                    pass

            logger.info("Content area theme updated successfully")

        except Exception as e:
            logger.error(f"Content theme update error: {e}")


class KeepAwakeProApp:
    """KeepAwake Pro — main application class"""

    def __init__(self):
        logger.info("Initializing KeepAwake Pro...")

        # Basic info
        self.version = "1.0"
        self.app_name = "KeepAwake Pro"

        # Setup directories
        self.data_dir = Path.home() / ".keepawake_pro"
        self.data_dir.mkdir(exist_ok=True)
        self.config_file = self.data_dir / "config.json"
        self.db_file = self.data_dir / "statistics.db"
        self.pid_file = self.data_dir / "app.pid"

        # Prevent multiple instances
        self._ensure_single_instance()

        # Load config
        self.config = self.load_config()

        # Initialize managers
        self.theme_manager = SimpleThemeManager()
        self.theme_manager.set_theme(self.config.get("theme", "dark"))

        self.smart_afk_manager = SmartAFKManager(self)

        # App state
        self.is_running = False
        self.is_paused = False
        self.session_start = None
        self.total_actions = 0
        self.worker_thread = None
        self._shutting_down = False
        self._quit_lock = threading.Lock()
        self._hotkey_listener = None

        # Performance metrics
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.uptime = "00:00:00"
        self._perf_stop_event = threading.Event()

        # Session stats cache (avoid hitting DB every second)
        self._cached_stats = ""
        self._last_stats_time = 0.0

        # GUI components
        self.root = None
        self.sidebar = None
        self.content_area = None
        self.tray_icon = None

        # Initialize
        self.init_database()
        self.init_gui()
        self.start_performance_monitoring()

        # Start smart AFK if enabled
        if self.config.get("smart_afk", False):
            self.smart_afk_manager.start()

        logger.info("KeepAwake Pro initialized successfully")

    def load_config(self):
        """Load configuration with defaults"""
        default_config = {
            "theme": "dark",
            "interval": 59,
            "auto_start": False,
            "smart_afk": False,
            "tray_enabled": True,
            "prevention_method": "f15",
            "schedule_enabled": False,
            "schedule_start": "09:00",
            "schedule_end": "17:00",
            "afk_probability": 0.25,
            "afk_min_duration": 30,
            "afk_max_duration": 120,
            "hotkeys": {
                "toggle": "<ctrl>+<alt>+k",
                "hide_show": "<ctrl>+<alt>+h"
            }
        }

        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict) and isinstance(config[key], dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in config[key]:
                                config[key][sub_key] = sub_value
                return config
        except Exception as e:
            logger.error(f"Config load error: {e}")

        return default_config

    def save_config(self):
        """Save configuration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Config save error: {e}")

    def _ensure_single_instance(self):
        """Prevent multiple instances via PID file. Exits if another instance is already running."""
        if self.pid_file.exists():
            try:
                old_pid = int(self.pid_file.read_text().strip())
                if MONITORING_AVAILABLE and psutil.pid_exists(old_pid):
                    # A live instance is already running — warn and bail out
                    try:
                        root = tk.Tk()
                        root.withdraw()
                        messagebox.showwarning(
                            "KeepAwake Pro",
                            "KeepAwake Pro is already running.\nCheck your system tray."
                        )
                        root.destroy()
                    except Exception:
                        pass
                    logger.info("Duplicate instance detected — exiting.")
                    sys.exit(0)
            except (ValueError, OSError):
                pass
            # Stale or corrupt PID file — remove it
            try:
                self.pid_file.unlink()
            except OSError:
                pass

        # Register this instance
        try:
            self.pid_file.write_text(str(os.getpid()))
        except OSError as e:
            logger.warning(f"Could not write PID file: {e}")

    def init_database(self):
        """Initialize database"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration INTEGER,
                    actions_count INTEGER,
                    method TEXT DEFAULT 'f15_keypress'
                )
            """)

            conn.commit()
            conn.close()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")

    def init_gui(self):
        """Initialize GUI with comprehensive error handling"""
        try:
            logger.info("Creating main window...")

            # Create main window
            self.root = ctk.CTk()
            self.root.title(self.app_name)
            self.root.geometry("900x600")
            self.root.minsize(800, 500)

            # Set theme
            ctk.set_appearance_mode(self.config.get("theme", "dark"))

            # Create main layout
            main_container = ctk.CTkFrame(self.root, corner_radius=0)
            main_container.pack(fill="both", expand=True)

            # Create sidebar
            logger.info("Creating sidebar...")
            self.sidebar = RobustSidebar(main_container, self)

            # Create content area
            logger.info("Creating content area...")
            self.content_area = RobustContentArea(main_container, self)

            # Setup window events
            self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

            # Start GUI updates
            self.schedule_gui_update()

            # Setup system tray icon (must happen after mainloop is ready)
            if TRAY_AVAILABLE and self.config.get("tray_enabled", True):
                self.root.after(500, self.setup_tray_icon)

            # Setup global hotkeys
            self.setup_hotkeys()

            logger.info("GUI initialized successfully")

        except Exception as e:
            logger.error(f"GUI initialization failed: {e}")
            raise

    def setup_tray_icon(self):
        """Create and start the system tray icon"""
        try:
            # Draw a simple shield icon
            icon_size = 64
            image = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse([4, 4, 60, 60], fill='#0e639c')
            draw.polygon([(32, 14), (50, 22), (50, 38), (32, 52), (14, 38), (14, 22)], fill='#ffffff')

            menu = pystray.Menu(
                pystray.MenuItem("Show", lambda icon, item: self.root.after(0, self.show_window)),
                pystray.MenuItem("Quit", lambda icon, item: self.root.after(0, self.quit_completely))
            )

            self.tray_icon = pystray.Icon(
                "KeepAwake Pro",
                image,
                "KeepAwake Pro",
                menu
            )

            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
            logger.info("System tray icon started")

        except Exception as e:
            logger.error(f"Tray icon setup error: {e}")
            self.tray_icon = None

    def show_window(self):
        """Restore window from tray"""
        try:
            if self.root:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
        except Exception as e:
            logger.error(f"Show window error: {e}")

    def _toggle_window_visibility(self):
        """Toggle window between visible and hidden"""
        try:
            if self.root.state() == 'withdrawn':
                self.show_window()
            else:
                self.root.withdraw()
        except Exception as e:
            logger.error(f"Window visibility toggle error: {e}")

    def setup_hotkeys(self):
        """Register global keyboard hotkeys using pynput"""
        if not INPUT_AVAILABLE:
            logger.warning("Hotkeys not available — pynput not installed")
            return
        try:
            hotkey_config = self.config.get("hotkeys", {})
            toggle_str = hotkey_config.get("toggle", "<ctrl>+<alt>+k")
            hide_show_str = hotkey_config.get("hide_show", "<ctrl>+<alt>+h")

            def parse_hotkey(hotkey_str):
                """Convert '<ctrl>+<alt>+k' into a frozenset of Key/KeyCode objects"""
                parts = hotkey_str.lower().split("+")
                keys = set()
                for part in parts:
                    part = part.strip()
                    if part.startswith("<") and part.endswith(">"):
                        key_name = part[1:-1]
                        try:
                            keys.add(getattr(Key, key_name))
                        except AttributeError:
                            logger.warning(f"Unknown key name in hotkey: {key_name}")
                    else:
                        keys.add(keyboard.KeyCode.from_char(part))
                return frozenset(keys)

            toggle_hotkey = parse_hotkey(toggle_str)
            hide_show_hotkey = parse_hotkey(hide_show_str)
            pressed_keys = set()

            def on_press(key):
                pressed_keys.add(key)
                current = frozenset(pressed_keys)
                if current == toggle_hotkey:
                    if self.root and not self._shutting_down:
                        self.root.after(0, self.toggle_prevention)
                elif current == hide_show_hotkey:
                    if self.root and not self._shutting_down:
                        self.root.after(0, self._toggle_window_visibility)

            def on_release(key):
                pressed_keys.discard(key)

            self._hotkey_listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
                daemon=True
            )
            self._hotkey_listener.start()
            logger.info(f"Hotkeys registered — toggle: {toggle_str}, hide/show: {hide_show_str}")

        except Exception as e:
            logger.error(f"Hotkey setup error: {e}")
            self._hotkey_listener = None

    def schedule_gui_update(self):
        """Schedule GUI updates"""
        if self._shutting_down:
            return
        try:
            self.update_gui()
        except Exception as e:
            logger.error(f"GUI update error: {e}")
        finally:
            if self.root and not self._shutting_down:
                self.root.after(1000, self.schedule_gui_update)

    def update_gui(self):
        """Update GUI elements"""
        try:
            if not self.content_area:
                return

            # Calculate session time
            session_time = "00:00:00"
            if self.session_start:
                delta = datetime.now() - self.session_start
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                session_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            stats_text = f"Actions: {self.total_actions} | Session: {session_time}"

            # Update dashboard
            self.content_area.update_dashboard(
                self.is_running,
                self.is_paused,
                stats_text,
                self.cpu_usage,
                self.memory_usage,
                self.uptime
            )

            # Update performance tab
            session_stats = self.get_session_stats()
            self.content_area.update_performance(
                self.cpu_usage,
                self.memory_usage,
                self.uptime,
                session_stats
            )

            # Update sidebar status
            if self.sidebar:
                self.sidebar.update_status(self.is_running)

        except Exception as e:
            logger.error(f"GUI update error: {e}")

    def start_performance_monitoring(self):
        """Start performance monitoring"""
        if not MONITORING_AVAILABLE:
            return

        def monitor():
            logger.info("Performance monitoring started")
            process = psutil.Process()
            while not self._perf_stop_event.is_set():
                try:
                    self.cpu_usage = process.cpu_percent(interval=0.1)
                    self.memory_usage = process.memory_info().rss / 1024 / 1024

                    # Calculate uptime
                    create_time = datetime.fromtimestamp(process.create_time())
                    uptime_delta = datetime.now() - create_time
                    hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                    self._perf_stop_event.wait(timeout=2)

                except Exception as e:
                    logger.error(f"Performance monitoring error: {e}")
                    self._perf_stop_event.wait(timeout=10)
            logger.info("Performance monitoring stopped")

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    def switch_content(self, content_id):
        """Switch content area"""
        try:
            if self.content_area:
                self.content_area.show_content(content_id)
        except Exception as e:
            logger.error(f"Content switch error: {e}")

    def toggle_theme(self):
        """Toggle theme and fully rebuild content area so all widget colors update"""
        try:
            new_theme = self.theme_manager.toggle_theme()

            # Update config
            self.config["theme"] = new_theme
            self.save_config()

            # Update CustomTkinter appearance
            ctk.set_appearance_mode(new_theme)

            # Save current UI state before rebuilding
            current_tab = self.sidebar.current_tab if self.sidebar else "dashboard"
            saved_interval = str(self.config.get("interval", 59))
            try:
                if self.content_area and hasattr(self.content_area, 'interval_entry'):
                    raw = self.content_area.interval_entry.get()
                    saved_interval = raw
                    # Also commit to config if valid so the value isn't lost
                    val = int(raw)
                    if val >= 10:
                        self.config["interval"] = val
            except Exception:
                pass

            # Update sidebar (stores references to all its own buttons)
            try:
                if self.sidebar:
                    self.sidebar.update_theme()
            except Exception as e:
                logger.error(f"Sidebar theme update failed: {e}")

            # Rebuild content area so every widget gets fresh colors
            try:
                if self.content_area:
                    parent = self.content_area.parent
                    self.content_area.main_frame.destroy()
                    self.content_area = RobustContentArea(parent, self)
                    # Restore settings field value
                    try:
                        self.content_area.interval_entry.delete(0, "end")
                        self.content_area.interval_entry.insert(0, saved_interval)
                    except Exception:
                        pass
                    # Restore active tab
                    self.switch_content(current_tab)
                    if self.sidebar:
                        self.sidebar.current_tab = current_tab
            except Exception as e:
                logger.error(f"Content area rebuild failed: {e}")

            logger.info(f"Theme switched to {new_theme}")

        except Exception as e:
            logger.error(f"Theme toggle error: {e}")
            messagebox.showerror("Theme Error", f"Failed to switch theme: {e}")

    def toggle_prevention(self):
        """Toggle prevention on/off (hotkey path)"""
        try:
            if self.is_running:
                self.stop_prevention()
            else:
                self.start_prevention()
        except Exception as e:
            logger.error(f"Prevention toggle error: {e}")

    def on_main_button_click(self):
        """Dashboard main button — START / PAUSE / RESUME depending on state"""
        try:
            if not self.is_running:
                self.start_prevention()
            elif self.is_paused:
                self.resume_prevention()
            else:
                self.pause_prevention()
        except Exception as e:
            logger.error(f"Main button click error: {e}")

    def pause_prevention(self):
        """Pause prevention without ending the session"""
        if not self.is_running or self.is_paused:
            return
        self.is_paused = True
        logger.info("Prevention paused")

    def resume_prevention(self):
        """Resume a paused prevention session"""
        if not self.is_running or not self.is_paused:
            return
        self.is_paused = False
        logger.info("Prevention resumed")

    def start_prevention(self):
        """Start prevention"""
        try:
            interval = self.config.get("interval", 59)
            if interval < 10:
                messagebox.showerror("Error", "Interval must be at least 10 seconds")
                return

            self.is_running = True
            self.is_paused = False
            self.session_start = datetime.now()
            self.total_actions = 0

            # Reset AFK timer so it doesn't fire prematurely on restart
            self.smart_afk_manager.last_action_time = time.time()

            # Start worker thread
            self.worker_thread = threading.Thread(target=self.prevention_worker, daemon=True)
            self.worker_thread.start()

            logger.info(f"Prevention started with interval: {interval}s")

        except Exception as e:
            logger.error(f"Start prevention error: {e}")

    def stop_prevention(self):
        """Stop prevention"""
        try:
            self.is_running = False
            self.is_paused = False

            # Wait for worker to stop
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2)

            # Save session
            if self.session_start:
                self.save_session_stats()

            logger.info("Prevention stopped")

        except Exception as e:
            logger.error(f"Stop prevention error: {e}")

    def prevention_worker(self):
        """Prevention worker thread with smart AFK, pause, and schedule support"""
        logger.info("Prevention worker started")

        while self.is_running:
            try:
                # --- Schedule check ---
                if self.config.get("schedule_enabled", False):
                    now_str = datetime.now().strftime("%H:%M")
                    sched_start = self.config.get("schedule_start", "00:00")
                    sched_end = self.config.get("schedule_end", "23:59")
                    in_schedule = sched_start <= now_str <= sched_end
                    if not in_schedule:
                        # Outside hours — wait 30 s then re-check
                        for _ in range(300):
                            if not self.is_running:
                                break
                            time.sleep(0.1)
                        continue

                # --- Pause check ---
                if self.is_paused:
                    time.sleep(0.1)
                    continue

                # --- Perform action ---
                if not self.smart_afk_manager.is_afk_active():
                    self.perform_prevention_action()
                    self.total_actions += 1
                    self.smart_afk_manager.register_action()

                # --- Wait for next cycle (interruptible) ---
                base_interval = self.config.get("interval", 59)
                actual_interval = self.smart_afk_manager.get_smart_interval(base_interval)

                for _ in range(actual_interval * 10):
                    if not self.is_running or self.is_paused:
                        break
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Prevention worker error: {e}")
                time.sleep(5)

        logger.info("Prevention worker stopped")

    def perform_prevention_action(self):
        """Perform the chosen prevention action"""
        method = self.config.get("prevention_method", "f15")
        try:
            if INPUT_AVAILABLE:
                if method == "mouse_move":
                    from pynput.mouse import Controller as MouseController
                    mouse = MouseController()
                    mouse.move(1, 0)
                    mouse.move(-1, 0)
                    logger.debug("Mouse nudge sent")
                else:
                    controller = KeyboardController()
                    key_map = {
                        "f15": Key.f15,
                        "f16": Key.f16,
                        "scroll_lock": Key.scroll_lock,
                    }
                    key = key_map.get(method, Key.f15)
                    controller.press(key)
                    time.sleep(0.01)
                    controller.release(key)
                    logger.debug(f"{method} keypress sent")
            else:
                # Fallback when pynput not available
                temp_file = self.data_dir / f"action_{int(time.time())}.tmp"
                temp_file.write_text("keepawake_action")
                temp_file.unlink()
                logger.debug("Fallback action performed")

        except Exception as e:
            logger.error(f"Prevention action error: {e}")

    def save_session_stats(self):
        """Save session statistics"""
        try:
            if not self.session_start:
                return

            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            end_time = datetime.now()
            duration = int((end_time - self.session_start).total_seconds())

            cursor.execute("""
                INSERT INTO sessions (start_time, end_time, duration, actions_count, method)
                VALUES (?, ?, ?, ?, ?)
            """, (self.session_start, end_time, duration, self.total_actions, "f15_keypress"))

            conn.commit()
            conn.close()

            logger.info(f"Session saved: {duration}s, {self.total_actions} actions")

        except Exception as e:
            logger.error(f"Session save error: {e}")

    def get_session_stats(self):
        """Get session statistics (cached — DB only queried every 10 seconds)"""
        now = time.time()
        if now - self._last_stats_time < 10 and self._cached_stats:
            return self._cached_stats
        # Stamp now before the query so errors don't cause a tight retry loop
        self._last_stats_time = now
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Get total stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as sessions,
                    SUM(duration) as total_duration,
                    SUM(actions_count) as total_actions,
                    AVG(duration) as avg_duration
                FROM sessions
            """)
            total_stats = cursor.fetchone()

            # Get recent sessions
            cursor.execute("""
                SELECT start_time, duration, actions_count 
                FROM sessions 
                ORDER BY start_time DESC 
                LIMIT 5
            """)
            recent_sessions = cursor.fetchall()

            conn.close()

            text = "=== SESSION STATISTICS ===\n\n"

            if total_stats and total_stats[0]:
                sessions, duration, actions, avg_duration = total_stats

                duration = int(duration or 0)
                actions = int(actions or 0)
                avg_duration = int(avg_duration or 0)

                hours, remainder = divmod(duration, 3600)
                minutes, _ = divmod(remainder, 60)
                avg_hours, avg_remainder = divmod(avg_duration, 3600)
                avg_minutes, _ = divmod(avg_remainder, 60)

                text += f"📊 ALL TIME STATISTICS:\n"
                text += f"  Total Sessions: {sessions}\n"
                text += f"  Total Duration: {hours:02d}:{minutes:02d}\n"
                text += f"  Total Actions: {actions}\n"
                text += f"  Average Session: {avg_hours:02d}:{avg_minutes:02d}\n\n"

            if recent_sessions:
                text += f"🕐 RECENT SESSIONS:\n"
                for start_time, duration, actions in recent_sessions:
                    try:
                        if isinstance(start_time, str):
                            start_dt = datetime.fromisoformat(start_time)
                        else:
                            start_dt = start_time

                        duration = int(duration or 0)
                        actions = int(actions or 0)

                        hours, remainder = divmod(duration, 3600)
                        minutes, _ = divmod(remainder, 60)
                        text += f"  {start_dt.strftime('%m/%d %H:%M')} - {hours:02d}:{minutes:02d} ({actions} actions)\n"

                    except Exception as e:
                        duration = int(duration or 0)
                        actions = int(actions or 0)
                        text += f"  Session - {duration}s ({actions} actions)\n"

            self._cached_stats = text
            return text

        except Exception as e:
            logger.error(f"Session stats error: {e}")
            return self._cached_stats or "Error loading session statistics"

    def on_window_close(self):
        """Handle window close — hide to tray only if tray icon is actually running"""
        if self.tray_icon is not None and self.config.get("tray_enabled", True):
            self.root.withdraw()
        else:
            self.quit_completely()

    def quit_completely(self):
        """Complete application shutdown"""
        # Confirm if prevention is actively running
        if self.is_running and not self.is_paused and not self._shutting_down:
            try:
                if not messagebox.askyesno(
                    "Quit KeepAwake Pro",
                    "Prevention is currently running.\n\nSave the session and quit?"
                ):
                    return
            except Exception:
                pass

        if not self._quit_lock.acquire(blocking=False):
            return  # Already shutting down — prevent double execution
        try:
            logger.info("Shutting down KeepAwake Pro...")
            self._shutting_down = True

            # Stop prevention
            if self.is_running:
                self.stop_prevention()

            # Stop smart AFK
            self.smart_afk_manager.stop()

            # Stop performance monitor
            self._perf_stop_event.set()

            # Stop hotkey listener
            if self._hotkey_listener:
                try:
                    self._hotkey_listener.stop()
                except Exception:
                    pass

            # Stop tray icon — small delay lets Windows shell fully deregister the icon
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                    time.sleep(0.4)
                except Exception:
                    pass

            # Save config
            self.save_config()

            # Remove PID file so next launch is not blocked
            try:
                if self.pid_file.exists():
                    self.pid_file.unlink()
            except Exception:
                pass

            # Close GUI
            if self.root:
                self.root.quit()
                self.root.destroy()

            logger.info("Shutdown complete")

        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        finally:
            os._exit(0)

    def run(self):
        """Run the application"""
        try:
            logger.info(f"Starting {self.app_name} v{self.version}...")

            # Auto-start after mainloop is ready
            if self.config.get("auto_start", False):
                self.root.after(200, self.start_prevention)

            # Start main loop
            self.root.mainloop()

        except KeyboardInterrupt:
            self.quit_completely()
        except Exception as e:
            logger.error(f"Application run error: {e}")
            messagebox.showerror("Fatal Error", f"Application error:\n{e}")
            self.quit_completely()


def main():
    """Main entry point with comprehensive error handling"""
    try:
        app = KeepAwakeProApp()
        app.run()
    except Exception as e:
        logger.error(f"Fatal initialization error: {e}")
        try:
            messagebox.showerror(
                "KeepAwake Pro - Fatal Error", 
                f"Failed to start application:\n\n{e}\n\nCheck logs for details."
            )
        except:
            print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
