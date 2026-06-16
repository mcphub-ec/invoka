# Agent-First Documentation: Invoka MCP Server

## 1. Contexto General
Servidor MCP para emisión electrónica de comprobantes delegados mediante la plataforma
Invoka (Ecuador). Invoka mantiene créditos prepagados; el agente consume un crédito por
cada comprobante emitido exitosamente.

## 2. Tecnologías Principales
- **FastMCP 3.3.1**.
- **httpx**: Cliente HTTP asíncrono.
- Header `X-API-KEY` con `INVOKA_API_KEY`.

## 3. Reglas de Negocio
- **Cada tool genera un comprobante que consume un crédito Invoka**. Antes de llamar
  cualquier herramienta, confirma con el usuario que la información es correcta.
- IVA Ecuador: 15% estándar, 0% para "Tarifa 0%".
- Tipos de identificación: CEDULA (10), RUC (13), PASAPORTE (alnum), CONSUMIDOR_FINAL (9999999999999).

## 4. Variables de Entorno
- `INVOKA_API_KEY`: Token de autenticación. **Nunca pasar como parámetro de tool**.
- `INVOKA_BASE_URL`: URL base (default según `.env.example`).
- `INVOKA_HTTP_TIMEOUT`: Timeout HTTP en segundos.
- `MCP_HOST`, `MCP_PORT`, `MCP_TRANSPORT_MODE`.

## 5. Herramientas Principales (12 totales)
- `emitir_factura`: Emite una factura electrónica.
- `emitir_nota_credito`: Emite una nota de crédito.
- `consultar_estado_comprobante`: Verifica el estado de un comprobante emitido.
- Y 9 más (consultas, listados, anulaciones según API Invoka).

## 6. Consideraciones de Seguridad
- **IDEMPOTENCIA**: cada tool acepta un campo `reference` o `external_id`. ÚSALO siempre
  para evitar cobros duplicados por retries del LLM.
- No loguear `INVOKA_API_KEY` (un filtro de logging lo redacta automáticamente).
- Las herramientas que afectan créditos de la plataforma requieren confirmación explícita
  del usuario antes de invocarse.

## 7. Instrucciones para Edición de Código
- Las tools siguen el patrón `@mcp.tool()` con type hints.
- El cliente HTTP único está en `_request()` con manejo centralizado de errores.
- Mantener compat con la API Invoka documentada en `docs/openapi.json`.

## 8. Tests
- Pendiente: añadir tests para el cliente HTTP y al menos 1 happy path por tool.
