import json
import os
import re
from ui.icons import Icons

_translations_cache = {}
_radio_ref = None

def load_locales_for_instance(instance_name: str = "") -> dict:
    """Load all base .json files and apply instance-specific overrides."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locales_path = os.path.join(root_dir, "locales")
    
    trans = {}
    if not os.path.exists(locales_path):
        return trans

    # 1. Base languages (e.g. hu.json, en.json)
    for filename in os.listdir(locales_path):
        if filename.endswith(".json") and "_" not in filename:
            lang_code = filename[:-5]
            try:
                with open(os.path.join(locales_path, filename), "r", encoding="utf-8") as f:
                    trans[lang_code] = json.load(f)
            except Exception as e:
                print(f"Error loading base locale {filename}: {e}")

    # 2. Instance-specific overrides (e.g. hu_1.json, hu_2.json)
    inst = instance_name or os.environ.get("INSTANCE_NAME", "")
    if inst:
        for filename in os.listdir(locales_path):
            if filename.endswith(f"_{inst}.json"):
                lang_code = filename.split("_")[0]
                if lang_code in trans:
                    try:
                        with open(os.path.join(locales_path, filename), "r", encoding="utf-8") as f:
                            overrides = json.load(f)
                            trans[lang_code].update(overrides)
                    except Exception as e:
                        print(f"Error loading instance override {filename}: {e}")
    return trans

def load_locales(instance_name: str = "") -> dict:
    return load_locales_for_instance(instance_name)

def get_translations(instance_name: str = "") -> dict:
    inst = instance_name or os.environ.get("INSTANCE_NAME", "")
    if inst not in _translations_cache:
        _translations_cache[inst] = load_locales_for_instance(inst)
    return _translations_cache[inst]

def init_translate(radio_instance):
    global _radio_ref
    _radio_ref = radio_instance
    inst = getattr(radio_instance, "instance_name", "")
    _translations_cache[inst] = load_locales_for_instance(inst)

def t(key: str, radio=None, **kwargs) -> str:
    """
    Translates a key based on the current radio language and instance.
    Supports icon placeholders like {SYNC} and dynamic kwargs.
    """
    r = radio or _radio_ref
    inst = getattr(r, "instance_name", "") if r else os.environ.get("INSTANCE_NAME", "")
    lang = getattr(r, "language", "hu") if r else "hu"
    
    trans_map = get_translations(inst)
    lang_dict = trans_map.get(lang, trans_map.get("en", {}))
    text = lang_dict.get(key)
    
    if text is None:
        text = trans_map.get("en", {}).get(key, key)

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
