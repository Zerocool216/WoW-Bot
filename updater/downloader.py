"""
Downloader - Descarga y valida assets desde GitHub
"""

import os
import aiohttp
import asyncio
import hashlib
from typing import Optional
from pathlib import Path

import config
from .logger import UpdaterLogger

logger = UpdaterLogger.get_logger()

TEMP_DIR = os.path.join(config.DATA_DIR, "update_temp")
BACKUP_DIR = os.path.join(config.DATA_DIR, "backups")


class Downloader:
    """Descarga y valida assets de GitHub Releases"""

    @staticmethod
    def ensure_temp_dir() -> None:
        """Crea directorio temporal para descargas"""
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

    @staticmethod
    async def download_file(
        url: str, filename: str, timeout_seconds: int = config.UPDATE_TIMEOUT_SECONDS
    ) -> Optional[str]:
        """
        Descarga un archivo desde URL

        Args:
            url: URL completa del archivo (ej: https://github.com/.../releases/download/.../bot.zip)
            filename: Nombre del archivo a guardar
            timeout_seconds: Timeout para descarga

        Returns:
            Ruta del archivo descargado, o None si falla

        Example:
            >>> filepath = await Downloader.download_file(
            ...     "https://github.com/.../bot-1.0.3.zip",
            ...     "bot-update.zip"
            ... )
        """
        Downloader.ensure_temp_dir()
        filepath = os.path.join(TEMP_DIR, filename)

        try:
            logger.info(f"Descargando {url}...")

            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Error HTTP {response.status} descargando {url}")
                        return None

                    # Descargar en chunks para evitar cargar todo en memoria
                    with open(filepath, "wb") as f:
                        chunk_size = 1024 * 1024  # 1 MB chunks
                        downloaded = 0
                        async for chunk in response.content.iter_chunked(chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)
                            logger.debug(f"Descargado: {downloaded / (1024*1024):.1f} MB")

            file_size = os.path.getsize(filepath)
            logger.info(f"Descarga completada: {filepath} ({file_size} bytes)")
            return filepath

        except asyncio.TimeoutError:
            logger.error(f"Timeout descargando {url}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexión descargando: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
        except Exception as e:
            logger.error(f"Error inesperado descargando: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None

    @staticmethod
    def validate_file(filepath: str, min_size_bytes: int = 1000) -> bool:
        """
        Valida que un archivo descargado sea válido

        Args:
            filepath: Ruta del archivo a validar
            min_size_bytes: Tamaño mínimo esperado (default 1KB)

        Returns:
            True si el archivo es válido
        """
        if not os.path.exists(filepath):
            logger.error(f"Archivo no existe: {filepath}")
            return False

        file_size = os.path.getsize(filepath)
        if file_size < min_size_bytes:
            logger.error(f"Archivo muy pequeño ({file_size} bytes < {min_size_bytes} bytes)")
            return False

        # Verificar que sea un ZIP válido
        if filepath.endswith(".zip"):
            try:
                import zipfile
                with zipfile.ZipFile(filepath, "r") as z:
                    test_result = z.testzip()
                    if test_result is not None:
                        logger.error(f"ZIP corrupto: {test_result}")
                        return False
            except Exception as e:
                logger.error(f"Error validando ZIP: {e}")
                return False

        logger.info(f"Archivo validado correctamente: {filepath}")
        return True

    @staticmethod
    def calculate_hash(filepath: str, algorithm: str = "md5") -> str:
        """
        Calcula hash de un archivo

        Args:
            filepath: Ruta del archivo
            algorithm: Algoritmo de hash (md5, sha1, sha256)

        Returns:
            Hash hexadecimal del archivo
        """
        hash_obj = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    @staticmethod
    def cleanup_temp() -> None:
        """Limpia directorio temporal de descargas"""
        try:
            if os.path.exists(TEMP_DIR):
                import shutil
                shutil.rmtree(TEMP_DIR)
                logger.info("Directorio temporal limpiado")
        except Exception as e:
            logger.warning(f"No se pudo limpiar temp: {e}")

    @staticmethod
    def get_backup_path(version: str) -> str:
        """
        Obtiene ruta para backup de una versión

        Args:
            version: Versión (ej: "1.0.2")

        Returns:
            Ruta: "data/backups/bot-1.0.2.zip"
        """
        Downloader.ensure_temp_dir()
        return os.path.join(BACKUP_DIR, f"bot-{version}.zip")
