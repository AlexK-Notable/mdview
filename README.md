# mdview

**Read markdown without leaving your terminal workflow.**

You're in the terminal. You need to check a README. You could open it in VS Code, wait for it to load, lose your context. Or you could `cat` it and squint at raw markdown like an animal.

mdview is the middle ground. A lightweight GTK4 viewer that opens instantly, renders markdown properly, and matches your wallpaper colors because you're not a savage. Open, read, close. Back to work.

## Why This Exists

| Problem | How We Solve It |
|---------|-----------------|
| "VS Code is overkill for reading a README" | **Single-purpose** - opens in <100ms, does one thing well |
| "Raw markdown in terminal is hard to read" | **Proper rendering** - WebKit-based with syntax highlighting |
| "My tools don't match my theme" | **Wallust integration** - colors sync with your wallpaper |
| "I want to tweak the font/zoom" | **Configurable** - JSON config for fonts, zoom, line height |
| "I need to check multiple docs" | **Tabs** - open several files, switch between them |

## What Makes It Different

- **Instant**: GTK4 + WebKit, not Electron. Opens before you finish blinking.
- **Themed**: Wallust integration means it looks like it belongs on your desktop.
- **Minimal**: One Python file. No build step. No dependencies beyond GTK4.
- **Keyboard-friendly**: Zoom with `Ctrl+/-`, quit with `Ctrl+Q`, open files with `Ctrl+O`.

---

## Installation

```bash
# Clone it
git clone https://github.com/your-username/mdview
cd mdview

# Make it executable
chmod +x mdview.py

# Symlink to PATH (optional)
ln -s $(pwd)/mdview.py ~/.local/bin/mdview
```

### Dependencies

```bash
# Arch Linux / CachyOS
sudo pacman -S python python-gobject gtk4 libadwaita webkit2gtk-5.0 python-markdown
```

## Usage

```bash
# View a file
mdview README.md

# Open multiple files in tabs
mdview file1.md file2.md

# Open config
mdview --config
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open file |
| `Ctrl+W` | Close tab |
| `Ctrl+Q` | Quit |
| `Ctrl++` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Reset zoom |
| `Ctrl+E` | Edit in external editor |

## Configuration

Config lives at `~/.config/mdview/config.json`:

```json
{
  "zoom_level": 1.0,
  "font_family": "system-ui, sans-serif",
  "font_size": 16,
  "code_font": "JetBrains Mono, Fira Code, monospace",
  "line_height": 1.7,
  "max_width": 52,
  "editor": "micro",
  "terminal": "ghostty"
}
```

## Wallust Integration

Create a template at `~/.config/wallust/templates/mdview.css` and mdview will automatically use your wallpaper colors.

## Requirements

- Python 3.8+
- GTK4 + Libadwaita
- WebKit2GTK 5.0
- python-markdown

## License

MIT
