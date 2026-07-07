from bot.repositories.config_repo import ConfigRepository

class WoWConnectionState:
    """
    Servicio encargado de actualizar y persistir el estado de la conexión TCP de WoW en SQLite,
    permitiendo que la vista en Discord refleje cambios de red en tiempo real.
    """
    @staticmethod
    async def set_state(state: str, error: str = None, character: str = None):
        updates = {"wow_connection_state": state}
        if error is not None:
            updates["wow_last_error"] = error
        if character is not None:
            updates["wow_connected_char"] = character
        await ConfigRepository.update_config(updates)
