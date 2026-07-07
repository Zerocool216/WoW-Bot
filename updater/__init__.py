"""
Updater Module - Auto-update system for distributed bot installations
Componentes principales para verificación, descarga y aplicación de actualizaciones desde GitHub Releases
"""

from .version_manager import VersionManager
from .github_client import GitHubClient
from .downloader import Downloader
from .applicator import Applicator
from .logger import UpdaterLogger

__all__ = [
    "VersionManager",
    "GitHubClient", 
    "Downloader",
    "Applicator",
    "UpdaterLogger",
]

__version__ = "1.0.0"
