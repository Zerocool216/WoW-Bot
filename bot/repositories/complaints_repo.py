import logging
from typing import Any, Dict, List, Optional

import aiosqlite
import config

logger = logging.getLogger("ComplaintsRepository")


class ComplaintsRepository:
    @staticmethod
    async def create_complaint(
        requester_id: int,
        requester_name: str,
        requester_display_name: str,
        complaint_type: str,
        character_name: str,
        complaint_text: str,
        form_payload_json: str,
        evidence: str = "",
        status: str = "pendiente",
        source_panel_channel_id: Optional[int] = None,
    ) -> int:
        query = """
            INSERT INTO complaints (
                requester_id,
                requester_name,
                requester_display_name,
                type,
                character_name,
                complaint_text,
                form_payload_json,
                evidence,
                status,
                source_panel_channel_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            cursor = await db.execute(
                query,
                (
                    requester_id,
                    requester_name,
                    requester_display_name,
                    complaint_type,
                    character_name,
                    complaint_text,
                    form_payload_json,
                    evidence,
                    status,
                    source_panel_channel_id,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def get_complaint(complaint_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM complaints WHERE id = ?"
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (complaint_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def update_complaint(complaint_id: int, updates: Dict[str, Any]) -> bool:
        if not updates:
            return False
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        query = f"UPDATE complaints SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        values = list(updates.values()) + [complaint_id]
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, values)
            await db.commit()
        return True

    @staticmethod
    async def list_active_complaints(limit: int = 50) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM complaints
            WHERE status IN ('pendiente', 'tomado', 'esperando_usuario', 'respondido')
            ORDER BY created_at DESC
            LIMIT ?
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def list_all_complaints(limit: int = 100) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM complaints
            ORDER BY updated_at DESC
            LIMIT ?
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def find_active_complaint_by_user(requester_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM complaints
            WHERE requester_id = ?
              AND status IN ('pendiente', 'tomado', 'esperando_usuario', 'respondido')
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (requester_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def create_history(
        complaint_id: int,
        actor_id: int,
        actor_name: str,
        old_status: str,
        new_status: str,
        action_description: str,
    ) -> int:
        query = """
            INSERT INTO complaints_history (
                complaint_id,
                actor_id,
                actor_name,
                old_status,
                new_status,
                action_description,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            cursor = await db.execute(query, (complaint_id, actor_id, actor_name, old_status, new_status, action_description))
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def get_history(complaint_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM complaints_history
            WHERE complaint_id = ?
            ORDER BY created_at ASC
        """
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (complaint_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
