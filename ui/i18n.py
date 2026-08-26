import json
import os
import re
from ui.icons import Icons

_translations = {}
_radio_ref = None

def load_locales():
    """Load all .json files from the locales directory, handling instance overrides."""
    global _translations
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locales_path = os.path.join(root_dir, "locales")
    
    if not os.path.exists(locales_path):
        print(f"Warning: Locales path not found at {locales_path}")
        return

    # 1. First load base languages (e.g. hu.json, en.json)
    for filename in os.listdir(locales_path):
        if filename.endswith(".json") and "_" not in filename:
            lang_code = filename[:-5]
            try:
                with open(os.path.join(locales_path, filename), "r", encoding="utf-8") as f:
                    _translations[lang_code] = json.load(f)
            except Exception as e:
                print(f"Error loading base locale {filename}: {e}")

    # 2. Check for instance-specific overrides if INSTANCE_NAME is set
    instance_name = os.environ.get("INSTANCE_NAME")
    if instance_name:
        for filename in os.listdir(locales_path):
            if filename.endswith(f"_{instance_name}.json"):
                lang_code = filename.split("_")[0]
                if lang_code in _translations:
                    try:
                        with open(os.path.join(locales_path, filename), "r", encoding="utf-8") as f:
                            overrides = json.load(f)
                            _translations[lang_code].update(overrides)
                    except Exception as e:
                        print(f"Error loading instance override {filename}: {e}")

load_locales()

def init_translate(radio_instance):
    global _radio_ref
    _radio_ref = radio_instance

def t(key: str, **kwargs) -> str:
    """
    Translates a key based on the current radio language.
    Supports icon placeholders like {SYNC} and dynamic kwargs.
    """
    lang = "hu"
    if _radio_ref:
        lang = getattr(_radio_ref, "language", "hu")
    
    lang_dict = _translations.get(lang, _translations.get("en", {}))
    text = lang_dict.get(key)
    
    if text is None:
        text = _translations.get("en", {}).get(key, key)

    if isinstance(text, str) and "{" in text:
        placeholders = re.findall(r"\{([A-Z0-9_]+)\}", text)
        for p in placeholders:
            if hasattr(Icons, p):
                icon_val = getattr(Icons, p)
                text = text.replace(f"{{{p}}}", str(icon_val))
    
    if kwargs and isinstance(text, str):
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
            
    return text
