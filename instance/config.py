"""
Configuración de instancia Flask (instance/config.py).

Este archivo sobreescribe los valores de app.py y NO debe subirse a control
de versiones.  Las variables de entorno definidas en .env tienen prioridad.
"""
import os

# ─── Seguridad ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "calculadora-sueldos-dev-secret-change-in-production")

# ─── Base de datos ────────────────────────────────────────────────────────────
_base_dir = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(_base_dir, "sueldos.db"),
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ─── Subida de archivos ───────────────────────────────────────────────────────
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

# ─── Modo debug ───────────────────────────────────────────────────────────────
DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
