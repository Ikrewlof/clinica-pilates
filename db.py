import os
import sqlite3
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clinica.db")

def _normalize_es(s: str) -> str:
    if s is None:
        return ""
    # Quitar tildes/diacríticos y pasar a minúsculas
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.lower()

def _collate_es(a, b) -> int:
    na = _normalize_es(a)
    nb = _normalize_es(b)
    return (na > nb) - (na < nb)

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_collation("ES", _collate_es)
    return conn
