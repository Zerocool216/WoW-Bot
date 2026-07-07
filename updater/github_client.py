"""
GitHub Client - Consulta GitHub Releases API para obtener versiones disponibles
"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

import config
from .logger import UpdaterLogger

logger = UpdaterLogger.get_logger()


class GitHubClient:
    """Cliente para GitHub Releases API (sin token requerido para repos públicos)"""

    API_BASE = "https://api.github.com"
    TIMEOUT = config.UPDATE_TIMEOUT_SECONDS

    def __init__(
        self,
        owner: str = config.UPDATE_GITHUB_OWNER,
        repo: str = config.UPDATE_GITHUB_REPO,
    ):
        """
        Inicializa cliente GitHub

        Args:
            owner: Usuario/org propietario del repo (ej: "judecalles")
            repo: Nombre del repositorio (ej: "WoW-Bridge-Bot")
        """
        self.owner = owner
        self.repo = repo

    async def get_latest_release(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene la release más reciente del repositorio

        Returns:
            Dict con info de release:
            {
                "version": "1.0.2",
                "tag": "v1.0.2",
                "url": "https://github.com/.../releases/tag/v1.0.2",
                "download_url": "https://github.com/.../releases/download/v1.0.2/bot.zip",
                "prerelease": False,
                "created_at": "2026-07-07T15:30:00Z"
            }
            None si hay error

        Example:
            >>> async def main():
            ...     client = GitHubClient("judecalles", "WoW-Bridge-Bot")
            ...     release = await client.get_latest_release()
            ...     if release:
            ...         print(f"Latest: {release['version']}")
            >>> asyncio.run(main())
        """
        endpoint = f"{self.API_BASE}/repos/{self.owner}/{self.repo}/releases/latest"

        try:
            timeout = aiohttp.ClientTimeout(total=self.TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint) as response:
                    if response.status != 200:
                        logger.warning(
                            f"GitHub API responded with {response.status}: {await response.text()}"
                        )
                        return None

                    data = await response.json()
                    return self._parse_release(data)

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout al consultar GitHub ({self.TIMEOUT}s). Continuando sin actualización."
            )
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexión a GitHub: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado consultando GitHub: {e}")
            return None

    async def get_all_releases(self, limit: int = 10) -> list:
        """
        Obtiene las últimas releases del repositorio

        Args:
            limit: Máximo número de releases a obtener

        Returns:
            Lista de releases parseadas, ordenadas por fecha (más recientes primero)
        """
        endpoint = f"{self.API_BASE}/repos/{self.owner}/{self.repo}/releases"

        try:
            timeout = aiohttp.ClientTimeout(total=self.TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    endpoint, params={"per_page": limit, "page": 1}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"GitHub API responded with {response.status}")
                        return []

                    data = await response.json()
                    return [self._parse_release(r) for r in data if r]

        except Exception as e:
            logger.error(f"Error obteniendo releases de GitHub: {e}")
            return []

    def _parse_release(self, gh_release: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parsea respuesta de GitHub a formato interno

        Args:
            gh_release: Objeto release de GitHub API

        Returns:
            Dict parseado o None si es inválido
        """
        try:
            tag_name = gh_release.get("tag_name", "")
            prerelease = gh_release.get("prerelease", False)

            # Si es prerelease y no está habilitado, saltarlo
            if prerelease and not config.UPDATE_ALLOW_PRERELEASE:
                logger.debug(f"Saltando prerelease {tag_name}")
                return None

            # Extraer versión del tag (ej: "v1.0.2" → "1.0.2")
            version = tag_name.lstrip("v")

            # Buscar asset ZIP descargable
            download_url = None
            if gh_release.get("assets"):
                for asset in gh_release["assets"]:
                    if asset["name"].endswith(".zip"):
                        download_url = asset.get("browser_download_url")
                        break

            if not download_url:
                logger.warning(f"No hay asset ZIP en release {tag_name}")
                return None

            return {
                "version": version,
                "tag": tag_name,
                "url": gh_release.get("html_url"),
                "download_url": download_url,
                "prerelease": prerelease,
                "created_at": gh_release.get("created_at"),
            }

        except Exception as e:
            logger.error(f"Error parseando release: {e}")
            return None

    async def get_latest_compatible_release(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene la release más reciente compatible (no prerelease si está deshabilitado)

        Returns:
            Dict de release o None
        """
        return await self.get_latest_release()

    async def test_connection(self) -> bool:
        """
        Verifica conexión con GitHub

        Returns:
            True si la conexión es exitosa
        """
        try:
            endpoint = f"{self.API_BASE}/repos/{self.owner}/{self.repo}"
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint) as response:
                    return response.status == 200
        except Exception:
            return False
