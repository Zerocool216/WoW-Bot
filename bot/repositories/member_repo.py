import aiosqlite
import config
from typing import List, Dict, Any, Optional

class MemberRepository:
    @staticmethod
    async def log_rank_change(user_id: int, username: str, previous_rank: str, new_rank: str, changed_by: str):
        """
        Registra de manera asíncrona un cambio de rango (historial de progresión).
        """
        query = """
            INSERT INTO guild_member_ranks (user_id, username, previous_rank, new_rank, changed_by)
            VALUES (?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, (user_id, username, previous_rank, new_rank, changed_by))
            await db.commit()

    @staticmethod
    async def add_staff_note(user_id: int, username: str, staff_id: int, staff_username: str, note: str, suggested_action: str):
        """
        Guarda una nota administrativa de staff. 
        Cumple estrictamente con la política de no guardar datos privados como IPs o información real del usuario.
        """
        query = """
            INSERT INTO staff_notes (user_id, username, staff_id, staff_username, note, suggested_action)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, (user_id, username, staff_id, staff_username, note, suggested_action))
            await db.commit()

    @staticmethod
    async def get_staff_notes(user_id: int) -> List[Dict[str, Any]]:
        """
        Recupera el historial completo de incidencias/notas asociadas a un miembro.
        Optimizado gracias al índice idx_staff_notes_user.
        """
        query = "SELECT * FROM staff_notes WHERE user_id = ? ORDER BY created_at DESC"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (user_id,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_recent_notes(limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recupera las últimas N incidencias tomadas en la hermandad.
        """
        query = "SELECT * FROM staff_notes ORDER BY created_at DESC LIMIT ?"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_recent_rank_changes(limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recupera los últimos N cambios de rango en la progresión.
        """
        query = "SELECT * FROM guild_member_ranks ORDER BY changed_at DESC LIMIT ?"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_guild_rank_for_member(member_roles: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Determina de forma dinámica el rango oficial de guild de un Member leyendo su lista de roles.
        Usa la lista paramétrica config.GUILD_RANK_ROLES.
        Retorna un dict con:
            - 'name': Nombre del rol
            - 'tier': Posición de jerarquía (1 es el más alto, 12 el más bajo)
        Retorna None si el miembro no tiene ningún rol de la lista.
        """
        # Obtenemos los nombres de roles en minúscula para evitar problemas de mayúsculas/espacios
        member_role_names = [role.name.strip().lower() for role in member_roles]
        
        for index, rank_name in enumerate(config.GUILD_RANK_ROLES):
            if rank_name.strip().lower() in member_role_names:
                return {
                    "name": rank_name,
                    "tier": index + 1
                }
        return None
