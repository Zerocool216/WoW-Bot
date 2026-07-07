"""
Logger - Sistema de logging dedicado para el módulo updater
"""

import os
import logging
from logging.handlers import RotatingFileHandler

import config


class UpdaterLogger:
    """Logger centralizado para eventos de actualización"""

    _logger = None

    @staticmethod
    def get_logger(name: str = "Updater") -> logging.Logger:
        """
        Obtiene o crea el logger del updater

        Args:
            name: Nombre del logger

        Returns:
            Logger configurado
        """
        if UpdaterLogger._logger is not None:
            return UpdaterLogger._logger

        # Crear logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Crear directorio de logs si no existe
        os.makedirs(config.LOGS_DIR, exist_ok=True)

        # Handler para archivo (rotativo)
        log_file = os.path.join(config.LOGS_DIR, "updater.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)

        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formato de logging
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Agregar handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        UpdaterLogger._logger = logger
        return logger

    @staticmethod
    def reset() -> None:
        """Resetea el logger (útil para tests)"""
        UpdaterLogger._logger = None
