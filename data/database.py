import os
import aiosqlite
import config

async def init_db():
    if not os.path.exists(config.DATA_DIR):
        os.makedirs(config.DATA_DIR)
        
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bridge_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                canal_taberna_discord_id INTEGER,
                canal_guild_discord_id INTEGER,
                bridge_taberna_activo BOOLEAN DEFAULT 0,
                bridge_guild_activo BOOLEAN DEFAULT 0,
                panel_channel_id INTEGER,
                panel_message_id INTEGER,
                listener_activo BOOLEAN DEFAULT 0,
                chatlog_path TEXT DEFAULT 'C:\\Games\\World of Warcraft 3.3.5a\\Logs\\ChatLog.txt',
                adapter_activo BOOLEAN DEFAULT 0,
                adapter_tipo TEXT DEFAULT 'Headless',
                wow_connection_state TEXT DEFAULT '🔴 Desconectado',
                wow_last_error TEXT,
                wow_connected_char TEXT,
                ultimo_offset_leido INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT single_row CHECK (id = 1)
            )
        """)
        
        # Insertar fila inicial con los IDs por defecto configurados por el usuario si no existe
        await db.execute("""
            INSERT OR IGNORE INTO bridge_config (
                id, 
                canal_guild_discord_id, 
                canal_taberna_discord_id, 
                bridge_taberna_activo, 
                bridge_guild_activo, 
                adapter_activo
            ) VALUES (1, 1478103974363267217, 1502658282261844178, 1, 1, 1)
        """)
        
        # En caso de necesitar forzar la columna en bases de datos viejas (SQLite migración simple)
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN chatlog_path TEXT DEFAULT 'C:\\Games\\World of Warcraft 3.3.5a\\Logs\\ChatLog.txt'")
            await db.execute("ALTER TABLE bridge_config ADD COLUMN adapter_activo BOOLEAN DEFAULT 0")
            await db.execute("ALTER TABLE bridge_config ADD COLUMN adapter_tipo TEXT DEFAULT 'ChatLog'")
            await db.execute("ALTER TABLE bridge_config ADD COLUMN ultimo_offset_leido INTEGER DEFAULT 0")
        except:
            pass # Las columnas ya existen

        # WhatsApp config migrations
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN whatsapp_channel_id INTEGER DEFAULT 1480229242079023124")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN whatsapp_invite_url TEXT DEFAULT ''")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN whatsapp_qr_url TEXT DEFAULT ''")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN whatsapp_message_id INTEGER DEFAULT NULL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN last_gmotd_sent TEXT DEFAULT NULL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN rules_message_id INTEGER DEFAULT NULL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN last_reminder_type TEXT DEFAULT NULL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE bridge_config ADD COLUMN last_reminder_time TEXT DEFAULT NULL")
        except:
            pass

        # Migración de Agonía de Sombras para casos existentes
        async def add_case_column(column_def: str):
            try:
                await db.execute(f"ALTER TABLE agonias_cases ADD COLUMN {column_def}")
            except Exception:
                pass

        await add_case_column("character_name TEXT DEFAULT ''")
        await add_case_column("class_spec TEXT DEFAULT ''")
        await add_case_column("mains_alters TEXT DEFAULT ''")
        await add_case_column("availability TEXT DEFAULT ''")
        await add_case_column("agonia_status TEXT DEFAULT 'No iniciada'")
        await add_case_column("has_shadows_edge INTEGER DEFAULT 0")
        await add_case_column("guild_seniority TEXT DEFAULT ''")
        await add_case_column("evidence_notes TEXT")
        await add_case_column("commitment_text TEXT")
        await add_case_column("approved_by_user_id INTEGER")
        await add_case_column("approved_by_name TEXT")
        await add_case_column("started_at TIMESTAMP")
        await add_case_column("finished_at TIMESTAMP")
        await add_case_column("ticket_channel_id INTEGER")
        await add_case_column("active_card_channel_id INTEGER")
        await add_case_column("final_message_channel_id INTEGER")
        await add_case_column("updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        await add_case_column("public_note TEXT")
        await add_case_column("haruko_sync_state TEXT DEFAULT 'pending'")
        await add_case_column("haruko_error TEXT")
            
        # ==========================================
        # TABLAS DE GESTIÓN DE GUILD Y STAFF
        # ==========================================
        
        # Histórico de progresión de rangos
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_member_ranks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                previous_rank TEXT,
                new_rank TEXT,
                changed_by TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agonias_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER NOT NULL,
                requester_name TEXT NOT NULL,
                character_name TEXT NOT NULL,
                class_spec TEXT NOT NULL,
                mains_alters TEXT NOT NULL,
                availability TEXT NOT NULL,
                agonia_status TEXT NOT NULL,
                fragment_number INTEGER NOT NULL DEFAULT 0,
                has_shadows_edge INTEGER NOT NULL DEFAULT 0,
                guild_seniority TEXT NOT NULL,
                evidence_notes TEXT,
                commitment_text TEXT,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'pendiente',
                assigned_staff_id INTEGER,
                assigned_staff_name TEXT,
                approved_by_user_id INTEGER,
                approved_by_name TEXT,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                ticket_channel_id INTEGER,
                ticket_message_id INTEGER,
                active_card_channel_id INTEGER,
                active_card_message_id INTEGER,
                final_message_channel_id INTEGER,
                final_message_id INTEGER,
                public_note TEXT,
                haruko_sync_state TEXT DEFAULT 'pending',
                haruko_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agonias_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                actor_name TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(case_id) REFERENCES agonias_cases(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER NOT NULL,
                requester_name TEXT NOT NULL,
                requester_display_name TEXT,
                type TEXT NOT NULL,
                character_name TEXT,
                complaint_text TEXT,
                form_payload_json TEXT,
                evidence TEXT,
                status TEXT NOT NULL DEFAULT 'pendiente',
                guild_id INTEGER,
                channel_id INTEGER,
                ticket_channel_id INTEGER,
                ticket_message_id INTEGER,
                history_message_id INTEGER,
                assigned_staff_id INTEGER,
                assigned_staff_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by_id INTEGER,
                resolved_by_name TEXT,
                resolved_reason TEXT,
                resolution TEXT,
                source_panel_channel_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS complaints_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                actor_name TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                action_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(complaint_id) REFERENCES complaints(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agonia_progress_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                actor_name TEXT NOT NULL,
                old_state TEXT,
                new_state TEXT,
                fragment_number INTEGER,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(case_id) REFERENCES agonias_cases(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agonia_message_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                message_type TEXT NOT NULL,
                channel_id INTEGER,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(case_id) REFERENCES agonias_cases(id)
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_agonias_cases_requester ON agonias_cases(requester_id);
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_agonias_cases_status ON agonias_cases(status);
        """)
        
        # Notas administrativas y sugerencias de la IA
        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                staff_id INTEGER,
                staff_username TEXT,
                note TEXT,
                suggested_action TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices de rendimiento para consultas frecuentes por miembro
        await db.execute("CREATE INDEX IF NOT EXISTS idx_member_ranks_user ON guild_member_ranks(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_staff_notes_user ON staff_notes(user_id)")

        await db.commit()
