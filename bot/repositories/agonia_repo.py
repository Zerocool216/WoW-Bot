import aiosqlite
import config
from typing import List, Optional, Dict, Any

class AgoniaRepository:
    @staticmethod
    async def create_case(
        requester_id: int,
        requester_name: str,
        character_name: str,
        class_spec: str,
        mains_alters: str,
        availability: str,
        agonia_status: str,
        fragment_number: int,
        has_shadows_edge: int,
        guild_seniority: str,
        evidence_notes: str,
        commitment_text: str,
        description: str,
        status: str = 'pendiente'
    ) -> int:
        query = """
            INSERT INTO agonias_cases (
                requester_id,
                requester_name,
                character_name,
                class_spec,
                mains_alters,
                availability,
                agonia_status,
                fragment_number,
                has_shadows_edge,
                guild_seniority,
                evidence_notes,
                commitment_text,
                description,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            cursor = await db.execute(
                query,
                (
                    requester_id,
                    requester_name,
                    character_name,
                    class_spec,
                    mains_alters,
                    availability,
                    agonia_status,
                    fragment_number,
                    has_shadows_edge,
                    guild_seniority,
                    evidence_notes,
                    commitment_text,
                    description,
                    status,
                )
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def get_case(case_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM agonias_cases WHERE id = ?"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (case_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def find_active_case(requester_id: int, character_name: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM agonias_cases
            WHERE (requester_id = ? OR lower(character_name) = lower(?))
              AND status IN ('pendiente','tomado','mas_datos','aprobado','activo','pausado')
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (requester_id, character_name))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def has_finalized_case_for_character(character_name: str) -> bool:
        query = """
            SELECT 1 FROM agonias_cases
            WHERE lower(character_name) = lower(?)
              AND status = 'finalizado'
            LIMIT 1
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            cursor = await db.execute(query, (character_name,))
            row = await cursor.fetchone()
            return bool(row)

    @staticmethod
    async def update_case(case_id: int, updates: Dict[str, Any]):
        if not updates:
            return
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values())
        values.append(case_id)
        query = f"UPDATE agonias_cases SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, values)
            await db.commit()

    @staticmethod
    async def list_active_cases() -> List[Dict[str, Any]]:
        query = "SELECT * FROM agonias_cases WHERE status IN ('pendiente','tomado','mas_datos','aprobado','activo','pausado') ORDER BY created_at ASC"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def list_all_cases(limit: int = 50) -> List[Dict[str, Any]]:
        query = "SELECT * FROM agonias_cases ORDER BY created_at DESC LIMIT ?"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def create_history(case_id: int, actor_id: int, actor_name: str, old_status: str, new_status: str, note: str = ""):
        query = """
            INSERT INTO agonias_history (
                case_id,
                actor_id,
                actor_name,
                old_status,
                new_status,
                note
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, (case_id, actor_id, actor_name, old_status, new_status, note))
            await db.commit()

    @staticmethod
    async def create_progress_log(
        case_id: int,
        actor_id: int,
        actor_name: str,
        old_state: str,
        new_state: str,
        fragment_number: int,
        note: str
    ):
        query = """
            INSERT INTO agonia_progress_logs (
                case_id,
                actor_id,
                actor_name,
                old_state,
                new_state,
                fragment_number,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, (case_id, actor_id, actor_name, old_state, new_state, fragment_number, note))
            await db.commit()

    @staticmethod
    async def create_message_link(case_id: int, message_type: str, channel_id: int, message_id: int):
        query = """
            INSERT INTO agonia_message_links (
                case_id,
                message_type,
                channel_id,
                message_id
            ) VALUES (?, ?, ?, ?)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, (case_id, message_type, channel_id, message_id))
            await db.commit()

    @staticmethod
    async def get_message_links(case_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM agonia_message_links WHERE case_id = ? ORDER BY created_at ASC"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (case_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def get_case_history(case_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM agonias_history WHERE case_id = ? ORDER BY created_at ASC"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (case_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
