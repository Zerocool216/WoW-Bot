import aiosqlite
import config
from typing import Dict, Any

class ConfigRepository:
    @staticmethod
    async def get_config() -> Dict[str, Any]:
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM bridge_config WHERE id = 1")
            row = await cursor.fetchone()
            return dict(row) if row else {}

    @staticmethod
    async def update_config(updates: Dict[str, Any]):
        if not updates:
            return
            
        set_clauses = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values())
        
        query = f"UPDATE bridge_config SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = 1"
        
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(query, values)
            await db.commit()

    @staticmethod
    async def get_whatsapp_config() -> Dict[str, Any]:
        cfg = await ConfigRepository.get_config()
        return {
            "whatsapp_channel_id": cfg.get("whatsapp_channel_id"),
            "whatsapp_invite_url": cfg.get("whatsapp_invite_url", ""),
            "whatsapp_qr_url": cfg.get("whatsapp_qr_url", ""),
            "whatsapp_message_id": cfg.get("whatsapp_message_id")
        }

    @staticmethod
    async def set_whatsapp_config(invite_url: str, qr_url: str, channel_id: int):
        await ConfigRepository.update_config({
            "whatsapp_invite_url": invite_url,
            "whatsapp_qr_url": qr_url,
            "whatsapp_channel_id": channel_id
        })

    @staticmethod
    async def set_whatsapp_message_id(message_id: int | None):
        await ConfigRepository.update_config({
            "whatsapp_message_id": message_id
        })

    @staticmethod
    async def get_last_gmotd_sent() -> str:
        cfg = await ConfigRepository.get_config()
        return cfg.get("last_gmotd_sent") or ""

    @staticmethod
    async def set_last_gmotd_sent(motd_text: str):
        await ConfigRepository.update_config({
            "last_gmotd_sent": motd_text
        })

    @staticmethod
    async def get_rules_message_id() -> int | None:
        cfg = await ConfigRepository.get_config()
        val = cfg.get("rules_message_id")
        return int(val) if val else None

    @staticmethod
    async def set_rules_message_id(message_id: int | None):
        await ConfigRepository.update_config({
            "rules_message_id": message_id
        })

    @staticmethod
    async def get_last_reminder_info() -> tuple[str | None, str | None]:
        cfg = await ConfigRepository.get_config()
        return cfg.get("last_reminder_type"), cfg.get("last_reminder_time")

    @staticmethod
    async def set_last_reminder_info(reminder_type: str | None, reminder_time: str | None):
        await ConfigRepository.update_config({
            "last_reminder_type": reminder_type,
            "last_reminder_time": reminder_time
        })
