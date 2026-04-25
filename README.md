# 🇪🇨 MCP Invoka

Servidor Model Context Protocol (MCP) para la integración con **Invoka**.

Parte del ecosistema oficial de [MCP Hub Ecuador](https://github.com/mcphub-ec/hub).

> [!IMPORTANT]
> **🤖 Nota para Agentes IA:** Antes de interactuar con este servidor, por favor revisa el [Agent Cheatsheet](https://github.com/mcphub-ec/hub/blob/main/agent-cheatsheet.md) en nuestro Hub principal para comprender las reglas de negocio, cálculo de IVA (15%) y formatos de identificación de Ecuador.

## 🚀 Características

-   Emisión electrónica simplificada basada en créditos.
-   Delegación de firma electrónica.
-   **Arquitectura Enterprise:** Imágenes Docker ultra-ligeras con _Healthchecks_ nativos, logs estructurados en JSON y validación continua de seguridad.

## 🛠️ Herramientas Disponibles

-   `emitir_factura`: Genera una factura consumiendo créditos de la plataforma.
-   `emitir_nota_credito`: Emite una nota de crédito.

## 📦 Instalación y Configuración

### 1\. Variables de Entorno

Este servidor es completamente _stateless_. Copia el archivo `.env.example` a `.env` y configura tus datos. **Nunca hagas commit de este archivo.**

```env
INVOKA_API_KEY="tu_api_key_aqui"
```

### 2\. Despliegue con Docker (Recomendado)

Para entornos de producción o pruebas limpias, recomendamos usar nuestra imagen oficial alojada en GitHub Container Registry (`ghcr.io`).

**Vía Docker CLI:**

```bash
docker run -d \
  --name mcp-invoka \
  --env-file .env \
  ghcr.io/mcphub-ec/mcp-invoka:latest
```

**Vía Docker Compose:**

```yaml
services:
  mcp-invoka:
    image: ghcr.io/mcphub-ec/mcp-invoka:latest
    container_name: mcp-invoka
    env_file:
      - .env
    restart: unless-stopped
```

### 3\. Uso con Claude Desktop (Local)

Si deseas conectarlo directamente a tu cliente de Claude para desarrollo local, añade la siguiente configuración a tu archivo `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-invoka": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/ruta/absoluta/a/tu/.env",
        "ghcr.io/mcphub-ec/mcp-invoka:latest"
      ]
    }
  }
}
```

_(Nota: También puedes correrlo directamente con `python -m server` si clonas el repositorio y manejas tu propio entorno virtual)._

## 🔒 Seguridad y Gobernanza

Este proyecto sigue estándares estrictos de seguridad:

-   **Stateless:** No almacena credenciales ni certificados en bases de datos.
-   **Escaneo de Vulnerabilidades:** Cada Pull Request es analizado automáticamente con `bandit` y `detect-secrets`.
-   **Responsible Disclosure:** Si encuentras una vulnerabilidad, por favor no abras un Issue público. Revisa nuestro [SECURITY.md](https://github.com/mcphub-ec/hub/blob/main/SECURITY.md) y contáctanos directamente a `security@mcphub.ec`.

## 🤝 Contribuir

Si deseas proponer mejoras, por favor revisa nuestra [Guía de Contribución](https://github.com/mcphub-ec/hub/blob/main/CONTRIBUTING.md) en el repositorio central. ¡Todos los Pull Requests que pasen los checks de CI/CD son bienvenidos!
