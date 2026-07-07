"""
Applicator - Aplica actualizaciones de forma segura con backup y rollback
"""

import os
import shutil
import zipfile
from typing import Optional
from pathlib import Path

import config
from .logger import UpdaterLogger
from .version_manager import VersionManager
from .downloader import TEMP_DIR, BACKUP_DIR

logger = UpdaterLogger.get_logger()


class Applicator:
    """Aplica actualizaciones de forma atómica y segura"""

    @staticmethod
    def create_backup(current_version: str) -> Optional[str]:
        """
        Crea backup de la instalación actual

        Args:
            current_version: Versión actual (ej: "1.0.2")

        Returns:
            Ruta del backup creado, o None si falla

        Example:
            >>> backup_path = Applicator.create_backup("1.0.2")
            >>> if backup_path:
            ...     print(f"Backup guardado en {backup_path}")
        """
        backup_path = os.path.join(BACKUP_DIR, f"bot-{current_version}.zip")

        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)

            # No sobrescribir backup existente
            if os.path.exists(backup_path):
                logger.info(f"Backup ya existe, omitiendo: {backup_path}")
                return backup_path

            logger.info(f"Creando backup de v{current_version}...")

            # Crear ZIP del estado actual
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as z:
                for root, dirs, files in os.walk(config.BASE_DIR):
                    # Excluir directorios no necesarios
                    dirs[:] = [
                        d
                        for d in dirs
                        if d not in [".venv", ".git", "__pycache__", "logs", "data/update_temp", ".env"]
                    ]

                    for file in files:
                        if file in [".env"]:  # No incluir secretos
                            continue
                        filepath = os.path.join(root, file)
                        arcname = os.path.relpath(filepath, config.BASE_DIR)
                        z.write(filepath, arcname)

            backup_size = os.path.getsize(backup_path) / (1024 * 1024)  # MB
            logger.info(f"Backup creado: {backup_path} ({backup_size:.1f} MB)")
            return backup_path

        except Exception as e:
            logger.error(f"Error creando backup: {e}")
            return None

    @staticmethod
    def extract_update(zip_path: str, extract_to: str = TEMP_DIR) -> bool:
        """
        Extrae el archivo ZIP de actualización de forma segura

        Args:
            zip_path: Ruta del ZIP descargado
            extract_to: Directorio destino para extracción

        Returns:
            True si se extrae correctamente
        """
        try:
            logger.info(f"Extrayendo actualización: {zip_path}")
            os.makedirs(extract_to, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_to)

            logger.info(f"Actualización extraída a: {extract_to}")
            return True

        except zipfile.BadZipFile:
            logger.error(f"ZIP corrupto: {zip_path}")
            return False
        except Exception as e:
            logger.error(f"Error extrayendo ZIP: {e}")
            return False

    @staticmethod
    def apply_update(
        extracted_path: str, version: str, keep_previous_backups: int = config.UPDATE_BACKUP_COUNT
    ) -> bool:
        """
        Aplica la actualización reemplazando archivos en el directorio de instalación

        IMPORTANTE: Esta función debe ejecutarse ANTES de reiniciar el proceso del bot
        para evitar bloqueos de archivos.

        Args:
            extracted_path: Ruta de la carpeta extraída con los archivos nuevos
            version: Versión a instalar (ej: "1.0.3")
            keep_previous_backups: Cuántos backups anteriores mantener

        Returns:
            True si se aplicó correctamente

        Estrategia:
            1. Crear backup de versión actual
            2. Copiar archivos del extracted_path al base_dir
            3. Actualizar version.json
            4. Limpiar backups antiguos
            5. El bot se reinicia después (via script PS1)
        """
        try:
            current_version = VersionManager.get_current()
            logger.info(f"Aplicando actualización de v{current_version} a v{version}")

            # Paso 1: Crear backup de estado actual
            backup_path = Applicator.create_backup(current_version)
            if not backup_path:
                logger.error("No se pudo crear backup, abortando")
                return False

            # Paso 2: Copiar archivos nuevos (estrategia: copiar selectivamente)
            logger.info("Reemplazando archivos...")
            files_replaced = 0

            for root, dirs, files in os.walk(extracted_path):
                # No copiar directorios críticos
                dirs[:] = [d for d in dirs if d not in [".env", "logs", "data/backups", "data/update_temp"]]

                for file in files:
                    if file.startswith("."):
                        continue

                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, extracted_path)
                    dst_path = os.path.join(config.BASE_DIR, rel_path)

                    # Crear directorio destino si no existe
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                    try:
                        shutil.copy2(src_path, dst_path)
                        files_replaced += 1
                        logger.debug(f"Reemplazado: {rel_path}")
                    except Exception as e:
                        logger.error(f"Error copiando {rel_path}: {e}")
                        # Continuar con otros archivos (mejor tener parcial que nada)

            if files_replaced == 0:
                logger.error("No se reemplazó ningún archivo, posible error")
                return False

            logger.info(f"Reemplazados {files_replaced} archivos")

            # Paso 3: Actualizar version.json
            if not VersionManager.update_version(version):
                logger.error("Error actualizando version.json")
                return False

            logger.info(f"version.json actualizado a {version}")

            # Paso 4: Limpiar backups antiguos
            Applicator._cleanup_old_backups(keep_previous_backups)

            logger.info(f"✅ Actualización aplicada correctamente a v{version}")
            return True

        except Exception as e:
            logger.error(f"Error aplicando actualización: {e}")
            return False

    @staticmethod
    def _cleanup_old_backups(keep_count: int = 2) -> None:
        """
        Limpia backups antiguos, manteniendo solo los últimos N

        Args:
            keep_count: Cuántos backups mantener
        """
        try:
            if not os.path.exists(BACKUP_DIR):
                return

            backups = sorted(
                [f for f in os.listdir(BACKUP_DIR) if f.startswith("bot-") and f.endswith(".zip")],
                reverse=True,
            )

            for backup in backups[keep_count:]:
                backup_path = os.path.join(BACKUP_DIR, backup)
                os.remove(backup_path)
                logger.debug(f"Backup antiguo eliminado: {backup}")

        except Exception as e:
            logger.warning(f"Error limpiando backups antiguos: {e}")

    @staticmethod
    def rollback(version_to_restore: str) -> bool:
        """
        Revierte a una versión anterior restaurando desde backup

        Args:
            version_to_restore: Versión a restaurar (ej: "1.0.1")

        Returns:
            True si se revierte correctamente

        WARNING: Requiere reinicio del bot después
        """
        backup_path = os.path.join(BACKUP_DIR, f"bot-{version_to_restore}.zip")

        if not os.path.exists(backup_path):
            logger.error(f"Backup no encontrado: {backup_path}")
            return False

        try:
            logger.warning(f"Revirtiendo a v{version_to_restore}...")

            # Extraer backup a temp
            temp_restore = os.path.join(TEMP_DIR, "restore")
            os.makedirs(temp_restore, exist_ok=True)

            with zipfile.ZipFile(backup_path, "r") as z:
                z.extractall(temp_restore)

            # Aplicar restauración
            if Applicator.apply_update(temp_restore, version_to_restore):
                logger.info(f"✅ Restauración a v{version_to_restore} completada")
                return True
            else:
                logger.error("Error aplicando restauración")
                return False

        except Exception as e:
            logger.error(f"Error revirtiendo: {e}")
            return False

    @staticmethod
    def is_installation_valid() -> bool:
        """
        Valida que la instalación actual sea funcional

        Returns:
            True si la instalación parece válida
        """
        required_files = [
            os.path.join(config.BASE_DIR, "main.py"),
            os.path.join(config.BASE_DIR, "config.py"),
            os.path.join(config.DATA_DIR, "versions.json"),
        ]

        for file in required_files:
            if not os.path.exists(file):
                logger.error(f"Archivo requerido no encontrado: {file}")
                return False

        return True
