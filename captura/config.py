"""Configurações persistentes (~/.config/captura/settings.json) e caminhos padrão."""
import json, os, subprocess

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "captura")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


def _xdg(name, fallback):
    try:
        p = subprocess.run(["xdg-user-dir", name], capture_output=True, text=True, timeout=2).stdout.strip()
        return p or fallback
    except Exception:
        return fallback


def default_screenshots_dir():
    return os.path.join(_xdg("PICTURES", os.path.expanduser("~/Pictures")), "Capturas de Tela")


def default_recordings_dir():
    return os.path.join(_xdg("VIDEOS", os.path.expanduser("~/Videos")), "Gravações de Tela")


DEFAULTS = {
    # Captura
    "shot_autocopy_edits": True,        # Copiar as alterações automaticamente
    "shot_autosave": True,              # Salvar automaticamente as capturas originais
    "shot_dir": None,                   # None -> default_screenshots_dir()
    "shot_ask_save_edited": False,      # Pedir para salvar as capturas editadas
    "shot_multi_window": False,         # Várias janelas
    "shot_border": False,               # Adicionar borda a cada captura
    "shot_border_color": "#ff0000",
    "shot_border_width": 3,
    # Gravação
    "rec_autocopy_edits": True,
    "rec_autosave": True,
    "rec_dir": None,
    "rec_ask_save_edited": False,
    "rec_mic": False,
    "rec_system_audio": True,
    # Atalhos / aparência
    "use_print_key": False,
    "theme": "system",                  # system | light | dark
    # Estado da interface
    "shape": "rectangle",               # rectangle | window | fullscreen | freeform
    "delay": 0,                         # 0 | 3 | 5 | 10
    "mode": "photo",                    # photo | video
    "quick_markup": False,              # Marcação rápida (Ctrl+E)
    "infobar_dismissed": False,
    "pen_color": "#e61b1b", "pen_size": 4,
    "hl_color": "#ffe600", "hl_size": 12,
    "shape_kind": "rect", "shape_color": "#e61b1b", "shape_size": 3,
}


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                self.data.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        if self.data.get(k) != v:
            self.data[k] = v
            self.save()

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_FILE)

    @property
    def shot_directory(self):
        return self.data["shot_dir"] or default_screenshots_dir()

    @property
    def rec_directory(self):
        return self.data["rec_dir"] or default_recordings_dir()


settings = Settings()
