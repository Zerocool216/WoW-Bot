# Bot de Guild WoW 3.3.5a - Headless Client (Fase 4C)

Este proyecto implementa un bot de Discord para una hermandad de World of Warcraft 3.3.5a, conectándose nativamente al servidor como si fuera un jugador real (Headless Client) para leer la Taberna y la Hermandad.

## Arquitectura

El bot se conecta a través de TCP puro al emulador del servidor 3.3.5a usando el patrón arquitectónico del repositorio `wowchat`.

1.  **Auth Session (Puerto 3724)**: Negocia la autenticación con el servidor.
2.  **World Session (Puerto 8085)**: *(No implementado en esta fase)*. Entra al reino, envía la sesión autenticada, carga un personaje al mundo, mantiene el ping y extrae los paquetes binarios `SMSG_MESSAGECHAT` (Chat).

## Prueba Real del Auth Server (Hito 1)

En la Fase 4C hemos abandonado las simulaciones. El panel de Discord incluye ahora un botón para probar de verdad el *Handshake* criptográfico contra el servidor WoW.

### Configuración requerida en `.env`
```env
WOW_REALMLIST=logon.tuservidor.com  # La IP/Host real del servidor
WOW_ACCOUNT=TU_USUARIO              # Cuenta real
# (WOW_PASSWORD y WOW_CHARACTER no se usan en este primer hito de TCP, pero guárdalos)
```

### ¿Qué prueba hace el bot?
Al pulsar **Hito 1: Probar TCP Auth Server** en Discord, el bot:
1. Abre un Socket TCP asíncrono real a `WOW_REALMLIST:3724`.
2. Empaqueta tu cuenta en un byte-array binario (Opcode `0x00` - `AUTH_LOGON_CHALLENGE`) con la estructura exacta del cliente 3.3.5a (build 12340).
3. Lo envía por la red.
4. Espera hasta 5 segundos la respuesta binaria del emulador.

### ¿Qué estados puede devolver?
- **TCP_CONNECTED**: Logró abrir el puerto, pero falló después.
- **AUTH_CHALLENGE_SUCCESS**: El servidor reconoció el paquete, validó tu cuenta y devolvió los parámetros SRP6 (B, g, N, salt).
- **AUTH_PROOF_ACCEPTED**: El servidor aceptó la prueba matemática SRP6a generada por el bot. **(¡Login Exitoso en Auth Server!)**
- **WORLD_AUTH_SUCCESS**: Sesión aceptada en el World Server.
- **CHAR_ONLINE**: El personaje Harukoo ha entrado con éxito al reino Thalassa.
- **AUTH_PROOF_REJECTED**: La contraseña es incorrecta o la matemática falló.

## Fase 5 - Conexión al Mundo (Harukoo)

Esta fase marca el salto definitivo del Auth Server (puerto 3724) al **World Server (puerto 8085)**. El bot ahora utiliza la Session Key obtenida para autenticar la sesión de juego.

### ¿Qué hace esta fase?
1. Finaliza la autenticación SRP6a y extrae la Realm List.
2. Localiza el reino **Thalassa** en el servidor NaerZone.
3. Abre una segunda conexión TCP hacia el World Server.
4. Envía `CMSG_AUTH_SESSION` con el digest SHA1 calculado a partir de la Session Key.
5. Solicita la lista de personajes (`CMSG_CHAR_ENUM`).
6. Envía `CMSG_PLAYER_LOGIN` para entrar al mundo con **Harukoo**.

### Datos fijos del entorno
- **Realmlist**: `comunidad.naerzone.com`
- **Reino**: `Thalassa`
- **Personaje**: `Harukoo`

### Seguridad de Credenciales
Todas las credenciales se leen exclusivamente desde el archivo `.env`. El código tiene prohibido imprimir contraseñas en logs o embeds de Discord. El nombre de la cuenta se muestra enmascarado en los paneles de administración.

## Ejecución en Windows (Sistema Todo-en-Uno)

He simplificado el proceso de arranque. Ya no necesitas ejecutar varios archivos; el script `WOW-BOT.bat` se encarga de todo de forma inteligente.

### Instrucciones de uso:
1.  **Instalar Python**: Asegúrate de tener [Python 3.8+](https://www.python.org/downloads/) instalado y marcado en el PATH.
2.  **Ejecutar**: Haz doble clic en `WOW-BOT.bat`.

### ¿Qué hace este script automáticamente?
- **Verifica Configuración**: Si no tienes un `.env`, lo crea por ti desde el ejemplo.
- **Gestiona el Entorno**: Si no tienes el entorno virtual `.venv` o faltan librerías, las instala automáticamente.
- **Inicia el Bot**: Una vez que todo está validado, arranca el bot y lo mantiene en ejecución.

## Política de Conservación del Núcleo Estable

Este proyecto prioriza la estabilidad y la fidelidad a los protocolos probados de WoW 3.3.5a.

### Principios de Desarrollo:
1. **Núcleo Protegido**: Los módulos de `wow_network` (`auth`, `world`, `crypto`) se consideran estables y no deben ser reescritos sin evidencia binaria de fallo.
2. **Restauración sobre Invención**: Si un flujo ya está resuelto en implementaciones estándar de WoW, se prefiere su restauración antes que una nueva implementación experimental.
3. **Adaptación Mínima**: Las variaciones específicas de servidores (como NaerZone) se implementan como capas de adaptación o orquestación, sin alterar el motor de paquetes base.

### Estructura de Capas:
- **Capa 1: Núcleo WoW**: Protocolo puro 3.3.5a.
- **Capa 2: Adaptación**: Lógica específica del servidor (NaerZone).
- **Capa 3: Bridge**: Integración con Discord y Panel.
- **Capa 4: Operación**: Configuración y arranque local.

---

## Despliegue 24/7 recomendado

Este proyecto no es una aplicación web tradicional. Es un **proceso persistente** que mantiene dos conexiones TCP abiertas constantemente (Discord API y WoW Server).

### Consideraciones técnicas
*   **No usar Hosting Web clásico**: Servicios como "cPanel Shared Hosting" no sirven porque matan procesos que duran más de unos minutos.
*   **Servidores PaaS (Railway/Render)**: Funcionan bien, pero a veces tienen límites de tiempo de ejecución o reinicios diarios que desconectarán al bot de WoW.
*   **VM/VPS (Recomendado)**: Una máquina virtual completa con Linux o Windows es la mejor opción para estabilidad total.

## Opciones de Hosting

| Opción | Pros | Contras |
| :--- | :--- | :--- |
| **PC Local** | Gratis, control total. | El bot se apaga si cierras la tapa o se va la luz. |
| **Oracle Cloud** | ¡Gratis para siempre! (Always Free). | Requiere tarjeta de crédito para validar cuenta. |
| **VPS Económica** | Muy estable, IP fija, 24/7 real. | Costo mensual (aprox $4-$6 USD). |
| **Railway / Render** | Fácil de desplegar. | Puede ser más caro o tener reinicios forzados. |

## Recomendación final de operación

1.  **Pruebas**: Usa tu **PC Local** con los scripts `.bat`. Es lo más rápido para ver cambios.
2.  **Producción**: Despliega en una **VPS (Ubuntu 22.04 recomendado)**. 
3.  **Estabilidad**: Para Linux, te recomiendo configurar un servicio `systemd` para que el bot se reinicie solo si el servidor de NaerZone se cae o hay un parpadeo de internet.

---

## Configuración específica de NaerZone - Thalassa
... (contenido anterior) ...

El bot está programado de forma predeterminada para atacar el ecosistema de **NaerZone**.

### Parámetros Exactos (.env)
- **Realmlist principal**: `comunidad.naerzone.com`
- **Reino objetivo**: `Thalassa`

Tus variables en el `.env` deben verse obligatoriamente así:
```env
WOW_REALMLIST=comunidad.naerzone.com
WOW_REALM=Thalassa
```

### Fallback Histórico
Si `comunidad.naerzone.com` sufre problemas de infraestructura o balanceo, puedes usar temporalmente:
`WOW_REALMLIST=thalassa.naerzone.com`
*(Nota: El valor principal y recomendado siempre será comunidad.naerzone.com)*

### Verificación Tolerante de Reino en Logs
Los emuladores pueden enviar el nombre del reino con ligeras variaciones de formato o espacios extra (ej: `" Thalassa "`). 
El sistema de red del bot (`_find_realm_tolerantly`) está programado para registrar cualquier realm devuelto por el servidor en la consola, y compararlo de forma tolerante (ignorando mayúsculas y espacios). 
- Si el log de red muestra `Realm devuelto por el servidor: ' Thalassa '`, el bot confirmará la coincidencia y continuará la conexión.
- Si hay un problema de DNS y el Auth Server no devuelve reinos, el bot detendrá la ejecución con un error `REALM_NOT_FOUND` y te sugerirá probar el fallback.

## Referencias de Diseño

1.  **[wowchat](https://github.com/fjaros/wowchat)**:
    *   **Tomado**: La arquitectura completa de emulación de cliente. Login nativo, separación estricta de `AuthSession` vs `WorldSession` y generación de paquetes binarios (`AuthPackets`).
    *   **Descartado**: El uso de Java/Scala, dependencias de bases de datos externas, y el parser de configuración nativo de Scala.
2.  **[legendarybot](https://github.com/greatman/legendarybot)**:
    *   **Tomado**: Privacidad administrativa (enmascaramiento de cuentas en UI y respuestas efímeras).
    *   **Descartado**: Toda la arquitectura de bots basados en comandos.
3.  **[gpt-discord-bot](https://github.com/openai/gpt-discord-bot)**:
    *   **Tomado**: Organización de variables críticas en `.env` y carga segura en `config.py`.
    *   **Descartado**: Lógica de IA.
