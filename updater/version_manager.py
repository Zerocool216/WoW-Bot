"""
Version Manager - Manejo centralizado de versionado semántico
Lee, compara y actualiza la versión local del bot
"""

import json
import os
from typing import Optional, Tuple
from datetime import datetime

import config

VERSION_FILE = os.path.join(config.DATA_DIR, "versions.json")


class VersionManager:
    """Gestor de versiones del bot con soporte para semantic versioning"""

    DEFAULT_STRUCTURE = {
        "current": "1.0.0",
        "release_date": datetime.utcnow().isoformat() + "Z",
        "previous": None,
        "check_time": None,
    }

    @staticmethod
    def _ensure_version_file_exists() -> None:
        """Crea archivo de versión si no existe"""
        if not os.path.exists(VERSION_FILE):
            os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                json.dump(VersionManager.DEFAULT_STRUCTURE, f, indent=2)

    @staticmethod
    def get_current() -> str:
        """
        Obtiene la versión actual instalada

        Returns:
            str: Versión semántica (ej: "1.0.2")
        """
        VersionManager._ensure_version_file_exists()
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("current", "1.0.0")
        except Exception:
            return "1.0.0"

    @staticmethod
    def get_all() -> dict:
        """
        Obtiene toda la metadata de versión

        Returns:
            dict: {"current": "...", "release_date": "...", "previous": "...", "check_time": "..."}
        """
        VersionManager._ensure_version_file_exists()
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return VersionManager.DEFAULT_STRUCTURE.copy()

    @staticmethod
    def update_version(new_version: str, release_date: Optional[str] = None) -> bool:
        """
        Actualiza la versión local

        Args:
            new_version: Nueva versión semántica (ej: "1.0.3")
            release_date: Fecha de release (ISO 8601, opcional)

        Returns:
            bool: True si se actualizó correctamente
        """
        VersionManager._ensure_version_file_exists()
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            old_version = data.get("current", "1.0.0")
            data["previous"] = old_version
            data["current"] = new_version
            data["release_date"] = release_date or datetime.utcnow().isoformat() + "Z"
            data["check_time"] = datetime.utcnow().isoformat() + "Z"

            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            return True
        except Exception:
            return False

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, int, int]:
        """
        Parsea string de versión a tupla numérica

        Args:
            version_str: Versión como "v1.0.2", "1.0.2", o "1.0.2-rc1"

        Returns:
            Tupla (major, minor, patch)

        Raises:
            ValueError: Si la versión no es semántica válida
        """
        version_str = str(version_str).strip()

        # Remover prefijo 'v' si existe
        if version_str.startswith("v"):
            version_str = version_str[1:]

        # Remover sufijo prerelease si existe (ej: -rc1, -beta, etc)
        if "-" in version_str:
            version_str = version_str.split("-")[0]

        # Parsear major.minor.patch
        try:
            parts = version_str.split(".")
            if len(parts) < 3:
                raise ValueError("Versión incompleta")
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            return (major, minor, patch)
        except (ValueError, IndexError) as e:
            raise ValueError(f"Versión inválida '{version_str}': {e}")

    @staticmethod
    def compare(version_a: str, version_b: str) -> int:
        """
        Compara dos versiones

        Args:
            version_a: Primera versión (ej: "1.0.2")
            version_b: Segunda versión (ej: "1.0.3")

        Returns:
            -1 si version_b es más nueva (actualización disponible)
            0 si son iguales
            1 si version_a es más nueva (downgrade)

        Example:
            >>> VersionManager.compare("1.0.2", "1.0.3")
            -1  # 1.0.3 es más nueva
        """
        try:
            a_tuple = VersionManager.parse_version(version_a)
            b_tuple = VersionManager.parse_version(version_b)

            if a_tuple < b_tuple:
                return -1  # b es más nueva
            elif a_tuple > b_tuple:
                return 1  # a es más nueva
            else:
                return 0  # iguales
        except ValueError:
            return 0  # En caso de error, asumir que no hay cambio

    @staticmethod
    def is_update_available(current: str, latest: str) -> bool:
        """
        Verifica si hay actualización disponible

        Args:
            current: Versión actual
            latest: Versión más reciente disponible

        Returns:
            bool: True si hay actualización disponible
        """
        return VersionManager.compare(current, latest) < 0

    @staticmethod
    def format_version(version_tuple: Tuple[int, int, int]) -> str:
        """
        Convierte tupla de versión a string

        Args:
            version_tuple: (major, minor, patch)

        Returns:
            str: "major.minor.patch"
        """
        return f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}"
