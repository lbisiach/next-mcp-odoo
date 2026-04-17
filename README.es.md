# MCP Server para Odoo

[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

Un servidor MCP que permite a asistentes de IA (Claude, Cursor, Copilot, Windsurf, Zed y cualquier cliente compatible con MCP) interactuar con sistemas Odoo ERP mediante lenguaje natural.

Compatible con **XML-RPC** (Odoo 14–19) y la nueva **API JSON-2** (Odoo 19+, nativa — sin módulo adicional requerido).

**¡Funciona con cualquier instancia de Odoo!** Usá el [modo YOLO](#modo-yolo-solo-para-desarrollopruebas-) para pruebas rápidas con cualquier instalación estándar de Odoo (XML-RPC), o usá el [modo JSON-2](#modo-json-2-odoo-19) para conectarte directamente a Odoo 19+ con solo una API key.

## Características

- 🔍 **Buscar y recuperar** cualquier registro de Odoo (clientes, productos, facturas, etc.)
- ✨ **Crear nuevos registros** con validación de campos y control de permisos
- ✏️ **Actualizar datos existentes** con manejo inteligente de campos
- 🗑️ **Eliminar registros** respetando los permisos del modelo
- ⚡ **Ejecutar cualquier acción de negocio** — validar facturas, confirmar pedidos, enviar mensajes, instalar módulos y más via `execute_method`
- 🔎 **Descubrir acciones de modelos** en tiempo real — encontrá el nombre correcto del método para cualquier versión de Odoo via `discover_model_actions`
- 🔢 **Contar registros** que coincidan con criterios específicos
- 📋 **Inspeccionar campos de modelos** para entender la estructura de datos
- 🔐 **Acceso seguro** con API key o autenticación usuario/contraseña
- 🎯 **Paginación inteligente** para conjuntos de datos grandes
- 🧠 **Selección inteligente de campos** — elige automáticamente los campos más relevantes por modelo
- 💬 **Salida optimizada para LLM** con formato de texto jerárquico
- 🌍 **Soporte multiidioma** — recibí respuestas en tu idioma preferido
- 🚀 **Modo YOLO** para acceso rápido a cualquier instancia de Odoo (XML-RPC, sin módulo)
- 🆕 **Protocolo JSON-2** — API nativa de Odoo 19+, sin módulo personalizado requerido

## Instalación

### Prerrequisitos

- Python 3.10 o superior
- Acceso a una instancia de Odoo:
  - **Modo estándar** (producción): Versión 16.0+ con el [módulo Odoo MCP](https://apps.odoo.com/apps/modules/19.0/mcp_server) instalado
  - **Modo JSON-2** (Odoo 19+): Solo requiere una API key, sin módulo adicional
  - **Modo YOLO** (pruebas/demos): Cualquier versión de Odoo con XML-RPC habilitado

### Instalar UV primero

El servidor MCP corre en tu **computadora local** (donde está instalado el cliente de IA), no en el servidor de Odoo. Instalá UV en tu máquina local:

<details>
<summary>macOS/Linux</summary>

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
</details>

<details>
<summary>Windows</summary>

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```
</details>

Reiniciá la terminal después de la instalación para que UV esté en el PATH.

### Instalación via configuración MCP (Recomendado)

Agregá esta configuración a tu cliente MCP:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://tu-instancia-odoo.com",
        "ODOO_API_KEY": "tu-api-key-aqui"
      }
    }
  }
}
```

<details>
<summary>Claude Desktop</summary>

Agregá a `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://tu-instancia-odoo.com",
        "ODOO_API_KEY": "tu-api-key-aqui",
        "ODOO_DB": "nombre-de-tu-base-de-datos"
      }
    }
  }
}
```
</details>

<details>
<summary>Claude Code</summary>

Agregá a `.mcp.json` en la raíz de tu proyecto:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://tu-instancia-odoo.com",
        "ODOO_API_KEY": "tu-api-key-aqui",
        "ODOO_DB": "nombre-de-tu-base-de-datos"
      }
    }
  }
}
```

O usá el CLI:

```bash
claude mcp add odoo \
  --env ODOO_URL=https://tu-instancia-odoo.com \
  --env ODOO_API_KEY=tu-api-key-aqui \
  --env ODOO_DB=nombre-de-tu-base-de-datos \
  -- uvx next-mcp-odoo
```
</details>

<details>
<summary>Cursor</summary>

Agregá a `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://tu-instancia-odoo.com",
        "ODOO_API_KEY": "tu-api-key-aqui",
        "ODOO_DB": "nombre-de-tu-base-de-datos"
      }
    }
  }
}
```
</details>

<details>
<summary>VS Code (con GitHub Copilot)</summary>

Agregá a `.vscode/mcp.json` en tu espacio de trabajo:

```json
{
  "servers": {
    "odoo": {
      "type": "stdio",
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://tu-instancia-odoo.com",
        "ODOO_API_KEY": "tu-api-key-aqui",
        "ODOO_DB": "nombre-de-tu-base-de-datos"
      }
    }
  }
}
```

> **Nota:** VS Code usa `"servers"` como clave raíz, no `"mcpServers"`.
</details>

<details>
<summary>Windsurf</summary>

Agregá a `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://tu-instancia-odoo.com",
        "ODOO_API_KEY": "tu-api-key-aqui",
        "ODOO_DB": "nombre-de-tu-base-de-datos"
      }
    }
  }
}
```
</details>

<details>
<summary>Zed</summary>

Agregá a `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "odoo": {
      "command": {
        "path": "uvx",
        "args": ["next-mcp-odoo"],
        "env": {
          "ODOO_URL": "https://tu-instancia-odoo.com",
          "ODOO_API_KEY": "tu-api-key-aqui",
          "ODOO_DB": "nombre-de-tu-base-de-datos"
        }
      }
    }
  }
}
```
</details>

### Métodos de instalación alternativos

<details>
<summary>Usando Docker</summary>

Corré con Docker — no requiere instalación de Python:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "ODOO_URL=http://host.docker.internal:8069",
        "-e", "ODOO_API_KEY=tu-api-key-aqui",
        "ivnvxd/mcp-server-odoo"
      ]
    }
  }
}
```

> **Nota:** Usá `host.docker.internal` en lugar de `localhost` para conectarte a Odoo corriendo en la máquina host.
</details>

<details>
<summary>Usando pip</summary>

```bash
pip install next-mcp-odoo
# o con entorno aislado
pipx install next-mcp-odoo
```

Luego usá `next-mcp-odoo` como comando en tu configuración MCP.
</details>

<details>
<summary>Desde el código fuente</summary>

```bash
git clone https://github.com/ivnvxd/mcp-server-odoo.git
cd mcp-server-odoo
pip install -e .
```
</details>

## Configuración

### Variables de entorno

| Variable | Requerida | Descripción | Ejemplo |
|----------|-----------|-------------|---------|
| `ODOO_URL` | Sí | URL de tu instancia Odoo | `https://miempresa.odoo.com` |
| `ODOO_API_KEY` | Sí* | API key para autenticación | `0ef5b399...` |
| `ODOO_USER` | Sí* | Usuario (si no usás API key) | `admin` |
| `ODOO_PASSWORD` | Sí* | Contraseña (requerida con `ODOO_USER`) | `admin` |
| `ODOO_DB` | No | Nombre de la base de datos (auto-detectada si no se especifica) | `miempresa` |
| `ODOO_API_PROTOCOL` | No | Protocolo API: `xmlrpc` (default) o `json2` | `json2` |
| `ODOO_EXECUTE_LEVEL` | No | Nivel de ejecución de métodos (ver abajo) | `business` |
| `ODOO_LOCALE` | No | Idioma/locale para las respuestas de Odoo | `es_AR` |
| `ODOO_YOLO` | No | Modo YOLO — solo XML-RPC, uso en desarrollo (⚠️) | `off`, `read`, `true` |

*`ODOO_API_KEY` es obligatorio para JSON-2. Para XML-RPC: `ODOO_API_KEY` o `ODOO_USER` + `ODOO_PASSWORD`.

#### `ODOO_EXECUTE_LEVEL` — controla `execute_method`

| Nivel | Qué permite |
|-------|------------|
| `safe` | Solo lectura. `execute_method` deshabilitado. |
| `business` | Cualquier método en modelos de negocio (`sale.*`, `account.*`, `mail.*`, etc.). Los modelos de sistema (`ir.*`, `res.users`, etc.) requieren `admin`. **Default.** |
| `admin` | Cualquier método en cualquier modelo incluyendo modelos de sistema/infraestructura. |

#### Configuración avanzada

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ODOO_MCP_DEFAULT_LIMIT` | `10` | Registros devueltos por búsqueda |
| `ODOO_MCP_MAX_LIMIT` | `100` | Límite máximo de registros por petición |
| `ODOO_MCP_MAX_SMART_FIELDS` | `15` | Máximo de campos en selección inteligente |
| `ODOO_MCP_LOG_LEVEL` | `INFO` | Nivel de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ODOO_MCP_LOG_JSON` | `false` | Habilitar salida de log JSON estructurado |
| `ODOO_MCP_LOG_FILE` | — | Ruta para archivo de log rotativo (10 MB, 5 backups) |
| `ODOO_MCP_TRANSPORT` | `stdio` | Tipo de transporte (`stdio`, `streamable-http`) |
| `ODOO_MCP_HOST` | `localhost` | Host para transporte HTTP |
| `ODOO_MCP_PORT` | `8000` | Puerto para transporte HTTP |

### Modo JSON-2 (Odoo 19+)

JSON-2 es la nueva API nativa de Odoo que reemplaza a XML-RPC. Solo requiere una API key — sin módulo MCP personalizado.

**`.env` de inicio rápido:**
```env
ODOO_URL=https://miodoo.ejemplo.com
ODOO_API_KEY=tu-api-key-aqui
ODOO_API_PROTOCOL=json2
ODOO_DB=mibd
ODOO_EXECUTE_LEVEL=business
```

**Configuración MCP:**
```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://miodoo.ejemplo.com",
        "ODOO_API_KEY": "tu-api-key-aqui",
        "ODOO_API_PROTOCOL": "json2",
        "ODOO_DB": "mibd",
        "ODOO_EXECUTE_LEVEL": "business"
      }
    }
  }
}
```

**Obtener una API key en Odoo:** Preferencias → Seguridad de la cuenta → Nueva clave de API

**Comparativa de protocolos:**

| | XML-RPC | JSON-2 |
|-|---------|--------|
| Versiones de Odoo | 14–19 (legacy en 20, eliminado en 22) | 19+ |
| Autenticación | API key o usuario/contraseña | Solo API key |
| Módulo personalizado requerido | Modo estándar: sí | No |
| Tool `execute_method` | Via modo YOLO | Via `execute_level` |

### Configuración de Odoo (modo XML-RPC estándar)

1. **Instalá el módulo MCP**:
   - Descargá el módulo [mcp_server](https://apps.odoo.com/apps/modules/19.0/mcp_server)
   - Instalalo en tu instancia de Odoo
   - Navegá a Configuración > Servidor MCP

2. **Habilitá modelos para acceso MCP**:
   - Ir a Configuración > Servidor MCP > Modelos habilitados
   - Agregá los modelos que querés acceder (ej: res.partner, product.product)
   - Configurá permisos (leer, escribir, crear, eliminar) por modelo

3. **Generá una API key**:
   - Ir a Configuración > Usuarios y Compañías > Usuarios
   - Seleccioná tu usuario
   - En la pestaña "Claves API", creá una nueva clave

### Modo YOLO (Solo para desarrollo/pruebas) ⚠️

El modo YOLO permite al servidor MCP conectarse directamente a cualquier instancia estándar de Odoo **sin requerir el módulo MCP**. Este modo omite todos los controles de seguridad MCP y está pensado **SOLO para desarrollo, pruebas y demos**.

**🚨 ADVERTENCIA: ¡Nunca uses el modo YOLO en entornos de producción!**

#### Niveles del modo YOLO

1. **Solo lectura** (`ODOO_YOLO=read`):
   - Permite todas las operaciones de lectura
   - Bloquea todas las operaciones de escritura
   - Seguro para demos y pruebas

2. **Acceso completo** (`ODOO_YOLO=true`):
   - Permite TODAS las operaciones sin restricciones
   - **EXTREMADAMENTE PELIGROSO** — usá solo en entornos aislados

<details>
<summary>Modo YOLO solo lectura</summary>

```json
{
  "mcpServers": {
    "odoo-demo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_USER": "admin",
        "ODOO_PASSWORD": "admin",
        "ODOO_DB": "demo",
        "ODOO_YOLO": "read"
      }
    }
  }
}
```
</details>

<details>
<summary>Modo YOLO acceso completo (⚠️ usar con extrema precaución)</summary>

```json
{
  "mcpServers": {
    "odoo-test": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_USER": "admin",
        "ODOO_PASSWORD": "admin",
        "ODOO_DB": "test",
        "ODOO_YOLO": "true"
      }
    }
  }
}
```
</details>

## Ejemplos de uso

Una vez configurado, podés pedirle al asistente:

**Búsqueda y consulta:**
- "Mostrame todos los clientes de Argentina"
- "Buscá productos con stock menor a 10 unidades"
- "Listá los pedidos de venta de hoy mayores a $1000"
- "Buscá facturas impagas del mes pasado"
- "¿Cuántos empleados activos tenemos?"
- "Mostrame el contacto de Microsoft"

**Crear y gestionar:**
- "Creá un nuevo contacto cliente para Acme S.A."
- "Agregá un producto 'Widget Premium' con precio $99.99"
- "Actualizá el teléfono del cliente Juan Pérez a +54-11-1234-5678"
- "Cambiá el estado del pedido SO/2024/001 a confirmado"
- "Eliminá el contacto de prueba que creamos antes"

**Acciones de negocio (via `execute_method`):**
- "Validá la factura FAC/2024/001"
- "Confirmá el pedido de venta SO/2024/005"
- "Mandá un mensaje al equipo en la OC PO/2024/010"
- "Registrá el pago de la factura 42"
- "Instalá el módulo de CRM"
- "Archivá todos los clientes inactivos"

## Herramientas disponibles

### `search_records`
Busca registros en cualquier modelo de Odoo con filtros.

```json
{
  "model": "res.partner",
  "domain": [["is_company", "=", true], ["country_id.code", "=", "AR"]],
  "fields": ["name", "email", "phone"],
  "limit": 10
}
```

### `get_record`
Recupera un registro específico por ID.

```json
{
  "model": "res.partner",
  "record_id": 42,
  "fields": ["name", "email", "street", "city"]
}
```

### `list_models`
Lista todos los modelos habilitados para acceso MCP.

### `list_resource_templates`
Lista las plantillas de URI de recursos disponibles.

### `create_record`
Crea un nuevo registro en Odoo.

```json
{
  "model": "res.partner",
  "values": {
    "name": "Nuevo Cliente",
    "email": "cliente@ejemplo.com",
    "is_company": true
  }
}
```

### `update_record`
Actualiza un registro existente.

```json
{
  "model": "res.partner",
  "record_id": 42,
  "values": {
    "phone": "+541112345678",
    "website": "https://ejemplo.com"
  }
}
```

### `delete_record`
Elimina un registro de Odoo.

```json
{
  "model": "res.partner",
  "record_id": 42
}
```

### `execute_method`
Ejecuta cualquier método o acción de negocio en un modelo de Odoo. Esta herramienta permite al asistente disparar acciones más allá del CRUD simple — validar facturas, confirmar pedidos, enviar mensajes en el chatter, instalar módulos, y todo lo que Odoo soporte.

El asistente resuelve automáticamente el modelo y método correcto basándose en tu pedido en lenguaje natural. Si no está seguro del nombre del método, puede usar `discover_model_actions` primero.

```json
{
  "model": "account.move",
  "method": "action_post",
  "ids": [42]
}
```

```json
{
  "model": "sale.order",
  "method": "message_post",
  "ids": [7],
  "kwargs": { "body": "Pedido revisado y aprobado." }
}
```

```json
{
  "model": "ir.module.module",
  "method": "button_immediate_install",
  "ids": [15]
}
```

**Control de acceso** mediante `ODOO_EXECUTE_LEVEL`:
- `safe` — deshabilitado
- `business` — permitido en modelos de negocio, bloqueado en modelos de sistema
- `admin` — permitido en todos los modelos

### `discover_model_actions`
Descubre los métodos y acciones disponibles para un modelo de Odoo en tiempo real. Consulta el registro de acciones del propio Odoo, por lo que siempre refleja la versión actual — sin nombres de métodos hardcodeados.

Usalo cuando no estés seguro de qué método llamar, o para verificar que un método existe antes de ejecutarlo. Esto hace que `execute_method` sea robusto ante actualizaciones de versión de Odoo.

```json
{
  "model": "account.move"
}
```

Devuelve server actions, window actions y métodos ORM comunes asociados al modelo.

### Selección inteligente de campos

Cuando omitís el parámetro `fields`, el servidor selecciona automáticamente los campos más relevantes usando un algoritmo de puntuación:

- **Campos esenciales** como `id`, `name`, `display_name` y `active` siempre se incluyen
- **Campos relevantes al negocio** (state, amount, email, phone, partner, etc.) tienen prioridad
- **Campos técnicos** (hilos de mensajes, seguimiento de actividades) se excluyen
- **Campos costosos** (binarios, HTML, texto grande, computados no almacenados) se omiten

El límite por defecto es 15 campos por petición. Podés ajustarlo con `ODOO_MCP_MAX_SMART_FIELDS` o saltarlo con `fields: ["__all__"]`.

## Recursos

El servidor también provee acceso directo a datos de Odoo via URIs de recursos:

| Patrón URI | Descripción |
|-----------|-------------|
| `odoo://{model}/record/{id}` | Obtener un registro específico por ID |
| `odoo://{model}/search` | Buscar registros con configuración por defecto (primeros 10) |
| `odoo://{model}/count` | Contar todos los registros de un modelo |
| `odoo://{model}/fields` | Obtener definiciones y metadata de campos |

**Ejemplos:**
- `odoo://res.partner/record/1` — Obtener el partner con ID 1
- `odoo://product.product/search` — Listar los primeros 10 productos
- `odoo://res.partner/count` — Contar todos los partners
- `odoo://product.product/fields` — Ver todos los campos de productos

## Cómo funciona

```
Asistente de IA (Claude, Cursor, Copilot, Windsurf, Zed, …)
        ↓ Protocolo MCP (stdio o HTTP)
   mcp-server-odoo
        ↓ XML-RPC (Odoo 14–19)  O  JSON-2 (Odoo 19+)
   Instancia de Odoo
```

El servidor traduce las llamadas de herramientas MCP en peticiones a la API de Odoo (XML-RPC o JSON-2 según `ODOO_API_PROTOCOL`). Se encarga de autenticación, control de acceso, selección de campos, formateo de datos y manejo de errores.

MCP es un protocolo abierto — cualquier cliente de IA compatible con MCP puede usar este servidor, no solo Claude.

## Seguridad

- Siempre usá HTTPS en entornos de producción
- Mantené tus API keys seguras y rotálas regularmente (Odoo las expira cada 3 meses)
- Para JSON-2, usá `ODOO_EXECUTE_LEVEL=business` (default) en producción
- El módulo MCP respeta los derechos de acceso y reglas de registro nativos de Odoo
- Cada API key está vinculada a un usuario específico con sus permisos

## Resolución de problemas

<details>
<summary>Problemas de conexión</summary>

Si recibís errores de conexión:
1. Verificá que la URL de Odoo sea correcta y accesible
2. Para XML-RPC estándar: verificá que el módulo MCP esté instalado visitando `https://tu-odoo.com/mcp/health`
3. Para JSON-2: verificá que la API key sea válida y que Odoo sea versión 19+
4. Asegurate de que el firewall permita conexiones a Odoo
</details>

<details>
<summary>Errores de autenticación</summary>

Si la autenticación falla:
1. Verificá que tu API key esté activa en Odoo (Preferencias → Seguridad de la cuenta)
2. Las API keys de Odoo expiran cada 3 meses — generá una nueva si es necesario
3. Verificá que el usuario tenga los permisos apropiados
4. Para JSON-2: solo se acepta API key, no usuario/contraseña
</details>

<details>
<summary>Errores de acceso a modelos</summary>

Si no podés acceder a ciertos modelos:
1. **XML-RPC estándar:** Ir a Configuración > Servidor MCP > Modelos habilitados en Odoo
2. **JSON-2:** Verificá `ODOO_EXECUTE_LEVEL` — los modelos de sistema requieren `admin`
3. Verificá que tu usuario tenga acceso al modelo en la configuración de seguridad de Odoo
</details>

<details>
<summary>Error "spawn uvx ENOENT"</summary>

Este error significa que UV no está instalado o no está en el PATH:

**Solución 1: Instalá UV** (ver sección de Instalación arriba)

**Solución 2: Problema de PATH en macOS**
Claude Desktop en macOS no hereda el PATH de tu shell. Probá:
1. Cerrá Claude Desktop completamente (Cmd+Q)
2. Abrí Terminal
3. Lanzá Claude desde Terminal:
   ```bash
   open -a "Claude"
   ```

**Solución 3: Usá la ruta completa**
```bash
which uvx
# Ejemplo: /Users/tunombre/.local/bin/uvx
```
Luego actualizá tu config con esa ruta completa.
</details>

<details>
<summary>Problemas de configuración de base de datos</summary>

Si ves "Access Denied" al listar bases de datos:
- Es normal — algunas instancias de Odoo restringen el listado por seguridad
- Especificá `ODOO_DB` en tu configuración

```json
{
  "env": {
    "ODOO_URL": "https://tu-odoo.com",
    "ODOO_API_KEY": "tu-clave",
    "ODOO_DB": "nombre-de-tu-base"
  }
}
```
</details>

<details>
<summary>Modo debug</summary>

Habilitá el log de debug para más información:

```json
{
  "env": {
    "ODOO_URL": "https://tu-odoo.com",
    "ODOO_API_KEY": "tu-clave",
    "ODOO_MCP_LOG_LEVEL": "DEBUG"
  }
}
```
</details>

## Desarrollo

<details>
<summary>Correr desde el código fuente</summary>

```bash
git clone https://github.com/ivnvxd/mcp-server-odoo.git
cd mcp-server-odoo
pip install -e ".[dev]"

# Correr tests
pytest --cov

# Correr el servidor
python -m next_mcp_odoo

# Verificar versión
python -m next_mcp_odoo --version
```
</details>

<details>
<summary>Probar con MCP Inspector</summary>

```bash
npx @modelcontextprotocol/inspector uvx next-mcp-odoo
```
</details>

## Tests

```bash
# Tests unitarios (sin Odoo)
uv run pytest -m "not yolo and not mcp" --cov

# Tests de integración YOLO (Odoo estándar, sin módulo MCP)
uv run pytest -m "yolo" -v

# Tests de integración MCP (Odoo + módulo MCP instalado)
uv run pytest -m "mcp" -v

# Todos los tests
uv run pytest --cov
```

## Licencia

Este proyecto está licenciado bajo Mozilla Public License 2.0 (MPL-2.0) — ver el archivo [LICENSE](LICENSE) para más detalles.

## Contribuciones

¡Las contribuciones son bienvenidas! Ver la guía [CONTRIBUTING](CONTRIBUTING.md) para más detalles.
