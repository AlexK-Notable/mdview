#!/usr/bin/env python3
"""
mdview - A lightweight markdown viewer with wallust theming
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

import argparse
import json
import subprocess
import sys
from pathlib import Path

import markdown
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, WebKit


CONFIG_DIR = Path.home() / ".config" / "mdview"
CONFIG_FILE = CONFIG_DIR / "config.json"
WALLUST_CSS = Path.home() / ".config" / "wallust" / "templates" / "mdview.css"
GENERATED_CSS = Path.home() / ".config" / "mdview" / "style.css"

DEFAULT_CONFIG = {
    # Display
    "zoom_level": 1.0,
    "font_family": "system-ui, -apple-system, sans-serif",
    "font_size": 16,
    "code_font": "JetBrains Mono, Fira Code, Consolas, monospace",
    "line_height": 1.7,
    "max_width": 52,
    # Behavior
    "auto_reload": False,
    "remember_position": True,
    "default_directory": "",
    # UI
    "show_status_bar": True,
    "custom_css_path": "",
    # Window
    "window_width": 900,
    "window_height": 700,
    "window_x": -1,
    "window_y": -1,
    # Tools
    "editor": "micro",
    "terminal": "ghostty",
    # State
    "last_files": []
}


def load_config() -> dict:
    """Load config from JSON file, creating default if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_CONFIG, **config}
        except json.JSONDecodeError:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save config to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_css(config: dict) -> str:
    """Load CSS from custom path, wallust-generated file, or fallback."""
    # Check for custom CSS path first
    custom_path = config.get("custom_css_path", "")
    if custom_path:
        custom_file = Path(custom_path).expanduser()
        if custom_file.exists():
            return custom_file.read_text()

    # Try wallust-generated CSS
    if GENERATED_CSS.exists():
        return GENERATED_CSS.read_text()

    # Fallback dark theme
    return """
    :root {
        --bg-color: #1e1e2e;
        --fg-color: #cdd6f4;
        --accent-color: #89b4fa;
        --code-bg: #313244;
        --border-color: #45475a;
    }
    body {
        background-color: var(--bg-color);
        color: var(--fg-color);
        font-family: system-ui, -apple-system, sans-serif;
        font-size: 16px;
        line-height: 1.6;
        padding: 2em;
        max-width: 50em;
        margin: 0 auto;
    }
    h1 { font-size: 2em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3em; }
    h2 { font-size: 1.5em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3em; }
    h3 { font-size: 1.25em; }
    h4 { font-size: 1em; }
    h5 { font-size: 0.875em; }
    h6 { font-size: 0.85em; }
    a { color: var(--accent-color); text-decoration: none; }
    a:hover { text-decoration: underline; }
    code {
        background-color: var(--code-bg);
        padding: 0.2em 0.4em;
        border-radius: 3px;
        font-family: monospace;
    }
    pre {
        background-color: var(--code-bg);
        padding: 1em;
        border-radius: 6px;
        overflow-x: auto;
    }
    pre code { padding: 0; background: none; }
    blockquote {
        border-left: 4px solid var(--accent-color);
        margin: 0;
        padding-left: 1em;
        color: var(--fg-color);
        opacity: 0.8;
    }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid var(--border-color); padding: 0.5em; }
    th { background-color: var(--code-bg); }
    img { max-width: 100%; }
    hr { border: none; border-top: 1px solid var(--border-color); }
    """


def get_config_overrides(config: dict) -> str:
    """Generate CSS overrides from config settings."""
    return f"""
    body {{
        font-family: {config.get('font_family', 'system-ui, sans-serif')};
        font-size: {config.get('font_size', 16)}px;
        line-height: {config.get('line_height', 1.7)};
        max-width: {config.get('max_width', 52)}em;
    }}
    code, pre code {{
        font-family: {config.get('code_font', 'monospace')};
    }}
    """


def render_markdown(md_content: str, css: str, config_overrides: str = "") -> str:
    """Convert markdown to styled HTML."""
    html_content = markdown.markdown(
        md_content,
        extensions=['fenced_code', 'tables', 'toc', 'nl2br', 'sane_lists']
    )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
    {css}
    {config_overrides}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


class MarkdownTab(Gtk.Box):
    """A tab containing a WebKit view for markdown content."""

    def __init__(self, file_path: Path | None = None, config: dict = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.file_path = file_path
        self.config = config or DEFAULT_CONFIG
        self.zoom_level = 1.0
        self.file_monitor = None

        # WebKit view
        self.webview = WebKit.WebView()
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)

        # WebKit settings for performance
        settings = self.webview.get_settings()
        settings.set_enable_smooth_scrolling(True)
        settings.set_enable_javascript(False)  # No need for JS
        settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.ALWAYS)
        settings.set_enable_back_forward_navigation_gestures(False)

        # Set opaque background to prevent Wayland transparency
        bg_color = Gdk.RGBA()
        bg_color.parse("#1e1e2e")  # Dark fallback, CSS will override
        self.webview.set_background_color(bg_color)

        # Disable default context menu (reload breaks markdown rendering)
        self.webview.connect("context-menu", lambda *args: True)

        self.append(self.webview)

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: Path):
        """Load and render a markdown file."""
        self.file_path = file_path
        try:
            content = file_path.read_text()
            css = load_css(self.config)
            overrides = get_config_overrides(self.config)
            html = render_markdown(content, css, overrides)
            self.webview.load_html(html, f"file://{file_path.parent}/")
            # Set up file monitoring if auto_reload enabled
            self._setup_file_monitor()
        except Exception as e:
            self.webview.load_html(f"<h1>Error</h1><pre>{e}</pre>", "")

    def _setup_file_monitor(self):
        """Set up file monitoring for auto-reload."""
        # Cancel existing monitor
        if self.file_monitor:
            self.file_monitor.cancel()
            self.file_monitor = None

        if not self.config.get("auto_reload", False) or not self.file_path:
            return

        gfile = Gio.File.new_for_path(str(self.file_path))
        self.file_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.file_monitor.connect("changed", self._on_file_changed)

    def _on_file_changed(self, monitor, file, other_file, event_type):
        """Handle file changes for auto-reload."""
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            # Small delay to ensure file is fully written
            GLib.timeout_add(100, self.reload)

    def reload(self):
        """Reload the current file."""
        if self.file_path:
            self.load_file(self.file_path)

    def set_zoom(self, level: float):
        """Set zoom level."""
        self.zoom_level = max(0.5, min(3.0, level))
        self.webview.set_zoom_level(self.zoom_level)

    def zoom_in(self):
        self.set_zoom(self.zoom_level + 0.1)

    def zoom_out(self):
        self.set_zoom(self.zoom_level - 0.1)

    def zoom_reset(self):
        self.set_zoom(1.0)

    def get_title(self) -> str:
        """Get tab title from filename."""
        if self.file_path:
            return self.file_path.name
        return "Untitled"


class MdViewWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, app, files: list[Path] = None):
        super().__init__(application=app)

        self.config = load_config()
        self.config_monitor = None
        self.set_default_size(
            self.config.get("window_width", 900),
            self.config.get("window_height", 700)
        )
        self.set_title("mdview")

        # Restore window position if enabled
        if self.config.get("remember_position", True):
            x = self.config.get("window_x", -1)
            y = self.config.get("window_y", -1)
            # Note: GTK4 doesn't support setting position directly on Wayland
            # Position is managed by the compositor

        # Connect close signal to save state
        self.connect("close-request", self.on_close_request)

        # Watch config file for changes
        self._setup_config_monitor()

        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        # Tab view
        self.tab_view = Adw.TabView()
        self.tab_view.set_vexpand(True)
        self.main_box.append(self.tab_view)

        # Tab bar (for multiple tabs)
        self.tab_bar = Adw.TabBar()
        self.tab_bar.set_view(self.tab_view)

        # Title label (for single tab - shows filepath)
        self.title_label = Gtk.Label(label="mdview")
        self.title_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_MIDDLE

        # Start with title label, switch to tab bar when multiple tabs
        self.header.set_title_widget(self.title_label)

        # Connect signals for tab changes
        self.tab_view.connect("notify::selected-page", self.on_tab_changed)
        self.tab_view.connect("page-attached", self.on_page_count_changed)
        self.tab_view.connect("page-detached", self.on_page_count_changed)

        # Status bar
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status_bar.add_css_class("toolbar")
        self.status_bar.set_margin_start(10)
        self.status_bar.set_margin_end(10)
        self.status_bar.set_margin_top(5)
        self.status_bar.set_margin_bottom(5)

        self.page_label = Gtk.Label(label="")
        self.status_bar.append(self.page_label)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.status_bar.append(spacer)

        self.zoom_label = Gtk.Label(label="100%")
        self.status_bar.append(self.zoom_label)

        self.main_box.append(self.status_bar)

        # Apply status bar visibility from config
        self.status_bar.set_visible(self.config.get("show_status_bar", True))

        # Header buttons
        self._setup_header_buttons()

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Open initial files or empty tab
        if files:
            for f in files:
                self.open_file(f)
        else:
            self.new_tab()

    def _setup_header_buttons(self):
        """Set up header bar buttons."""
        # Left side - Open file
        open_btn = Gtk.Button(icon_name="document-open-symbolic")
        open_btn.set_tooltip_text("Open file (Ctrl+O)")
        open_btn.connect("clicked", self.on_open_clicked)
        self.header.pack_start(open_btn)

        # Right side buttons
        # Zoom controls
        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        zoom_box.add_css_class("linked")

        zoom_out_btn = Gtk.Button(icon_name="zoom-out-symbolic")
        zoom_out_btn.set_tooltip_text("Zoom out (Ctrl+-)")
        zoom_out_btn.connect("clicked", lambda b: self.zoom_out())
        zoom_box.append(zoom_out_btn)

        zoom_reset_btn = Gtk.Button(icon_name="zoom-original-symbolic")
        zoom_reset_btn.set_tooltip_text("Reset zoom (Ctrl+0)")
        zoom_reset_btn.connect("clicked", lambda b: self.zoom_reset())
        zoom_box.append(zoom_reset_btn)

        zoom_in_btn = Gtk.Button(icon_name="zoom-in-symbolic")
        zoom_in_btn.set_tooltip_text("Zoom in (Ctrl++)")
        zoom_in_btn.connect("clicked", lambda b: self.zoom_in())
        zoom_box.append(zoom_in_btn)

        self.header.pack_end(zoom_box)

        # Settings button
        settings_btn = Gtk.Button(icon_name="emblem-system-symbolic")
        settings_btn.set_tooltip_text("Edit config")
        settings_btn.connect("clicked", self.on_settings_clicked)
        self.header.pack_end(settings_btn)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        self.add_controller(controller)

        shortcuts = [
            ("<Ctrl>o", self.on_open_shortcut),
            ("<Ctrl>w", self.close_current_tab),
            ("<Ctrl>t", self.new_tab),
            ("<Ctrl>r", self.reload_current),
            ("<Ctrl>plus", self.zoom_in),
            ("<Ctrl>equal", self.zoom_in),
            ("<Ctrl>minus", self.zoom_out),
            ("<Ctrl>0", self.zoom_reset),
            ("<Ctrl>q", lambda: self.close()),
        ]

        for accel, callback in shortcuts:
            shortcut = Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string(accel),
                action=Gtk.CallbackAction.new(lambda w, d, cb=callback: cb() or True)
            )
            controller.add_shortcut(shortcut)

    def new_tab(self, file_path: Path = None) -> MarkdownTab:
        """Create a new tab."""
        tab = MarkdownTab(file_path, config=self.config)
        tab.set_zoom(self.config.get("zoom_level", 1.0))

        page = self.tab_view.append(tab)
        page.set_title(tab.get_title())
        self.tab_view.set_selected_page(page)

        self.update_status()
        return tab

    def open_file(self, file_path: Path):
        """Open a file in a new tab."""
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            return

        # Check if already open
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            tab = page.get_child()
            if tab.file_path == file_path:
                self.tab_view.set_selected_page(page)
                return

        self.new_tab(file_path)

    def get_current_tab(self) -> MarkdownTab | None:
        """Get the currently selected tab."""
        page = self.tab_view.get_selected_page()
        if page:
            return page.get_child()
        return None

    def close_current_tab(self):
        """Close the current tab."""
        page = self.tab_view.get_selected_page()
        if page:
            self.tab_view.close_page(page)
        if self.tab_view.get_n_pages() == 0:
            self.close()

    def reload_current(self):
        """Reload current tab."""
        tab = self.get_current_tab()
        if tab:
            tab.reload()

    def zoom_in(self):
        tab = self.get_current_tab()
        if tab:
            tab.zoom_in()
            self.update_zoom_label(tab)

    def zoom_out(self):
        tab = self.get_current_tab()
        if tab:
            tab.zoom_out()
            self.update_zoom_label(tab)

    def zoom_reset(self):
        tab = self.get_current_tab()
        if tab:
            tab.zoom_reset()
            self.update_zoom_label(tab)

    def update_zoom_label(self, tab: MarkdownTab):
        """Update zoom percentage in status bar."""
        self.zoom_label.set_text(f"{int(tab.zoom_level * 100)}%")

    def update_status(self):
        """Update status bar and header title."""
        tab = self.get_current_tab()
        if tab:
            self.update_zoom_label(tab)
            if tab.file_path:
                self.page_label.set_text(str(tab.file_path))
                # Update title label for single-tab mode
                self.title_label.set_text(str(tab.file_path))
            else:
                self.page_label.set_text("")
                self.title_label.set_text("mdview")

    def on_tab_changed(self, tab_view, param):
        """Handle tab selection change."""
        self.update_status()

    def on_page_count_changed(self, tab_view, page, position=None):
        """Handle tab added/removed - toggle between tab bar and title."""
        n_pages = self.tab_view.get_n_pages()
        if n_pages > 1:
            self.header.set_title_widget(self.tab_bar)
        else:
            self.header.set_title_widget(self.title_label)
        self.update_status()

    def on_close_request(self, window):
        """Save window state on close."""
        # Save window size
        width, height = self.get_default_size()
        self.config["window_width"] = width
        self.config["window_height"] = height

        # Save open files
        open_files = []
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            tab = page.get_child()
            if tab.file_path:
                open_files.append(str(tab.file_path))
        self.config["last_files"] = open_files

        # Save current zoom level
        tab = self.get_current_tab()
        if tab:
            self.config["zoom_level"] = tab.zoom_level

        save_config(self.config)
        return False  # Allow close to proceed

    def _setup_config_monitor(self):
        """Watch config file for changes."""
        gfile = Gio.File.new_for_path(str(CONFIG_FILE))
        self.config_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.config_monitor.connect("changed", self._on_config_changed)

    def _on_config_changed(self, monitor, file, other_file, event_type):
        """Handle config file changes."""
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            # Reload config after small delay
            GLib.timeout_add(100, self._apply_config_changes)

    def _apply_config_changes(self):
        """Apply config changes to all tabs."""
        self.config = load_config()

        # Update status bar visibility
        self.status_bar.set_visible(self.config.get("show_status_bar", True))

        # Update all tabs with new config
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            tab = page.get_child()
            tab.config = self.config
            # Re-setup file monitors (for auto_reload changes)
            tab._setup_file_monitor()
            # Reload to apply new styling
            if tab.file_path:
                tab.reload()

        return False  # Don't repeat

    def on_open_clicked(self, button):
        """Handle open button click."""
        self.show_open_dialog()

    def on_open_shortcut(self):
        """Handle Ctrl+O."""
        self.show_open_dialog()

    def show_open_dialog(self):
        """Show file open dialog."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Markdown File")

        # Set initial directory from config
        default_dir = self.config.get("default_directory", "")
        if default_dir:
            dir_path = Path(default_dir).expanduser()
            if dir_path.exists():
                dialog.set_initial_folder(Gio.File.new_for_path(str(dir_path)))

        # File filter for markdown
        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files")
        filter_md.add_pattern("*.md")
        filter_md.add_pattern("*.markdown")
        filter_md.add_mime_type("text/markdown")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_md)
        filters.append(filter_all)
        dialog.set_filters(filters)

        dialog.open(self, None, self.on_open_dialog_response)

    def on_open_dialog_response(self, dialog, result):
        """Handle file dialog response."""
        try:
            file = dialog.open_finish(result)
            if file:
                self.open_file(Path(file.get_path()))
        except GLib.Error:
            pass  # User cancelled

    def on_settings_clicked(self, button):
        """Open config in editor (in terminal)."""
        save_config(self.config)  # Ensure file exists
        editor = self.config.get("editor", "micro")
        terminal = self.config.get("terminal", "ghostty")
        # Open editor in a terminal
        subprocess.Popen([terminal, "-e", editor, str(CONFIG_FILE)])


class MdViewApp(Adw.Application):
    """Main application class."""

    def __init__(self, files: list[Path] = None):
        super().__init__(application_id="com.github.mdview")
        self.files = files or []

    def do_activate(self):
        """Handle app activation."""
        win = MdViewWindow(self, self.files)
        win.present()


def main():
    parser = argparse.ArgumentParser(description="Lightweight markdown viewer")
    parser.add_argument("files", nargs="*", help="Markdown files to open")
    parser.add_argument("--config", "-c", action="store_true",
                        help="Open config file in editor")
    args = parser.parse_args()

    if args.config:
        config = load_config()
        save_config(config)  # Ensure file exists
        editor = config.get("editor", "micro")
        subprocess.run([editor, str(CONFIG_FILE)])
        return 0

    files = [Path(f) for f in args.files] if args.files else []
    app = MdViewApp(files)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
