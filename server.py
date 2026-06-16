"""
INVOKA MCP Server
=================
MCP server for the INVOKA API (invoka.com.ec) — credit-based electronic billing
platform for Ecuador (SRI). Issues invoices, credit notes, retentions, and
remittance guides. Manages companies, signatures, logos, and credit balance.

Auth: X-API-KEY header via INVOKA_API_KEY env var.
Technical reference: docs/openapi.json
"""

import os
import json
import logging
from typing import Any

from dotenv import load_dotenv
import httpx
from mcp.server.fastmcp import FastMCP

# Cargar variables desde el archivo .env
load_dotenv()


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "name":"%(name)s", "message":"%(message)s"}',
)
logger = logging.getLogger("invoka-mcp")

INVOKA_BASE_URL = os.environ.get(
    "INVOKA_BASE_URL", "https://www.invoka.com.ec"
)

HTTP_TIMEOUT = float(os.environ.get("INVOKA_HTTP_TIMEOUT", "30"))

mcp = FastMCP(
    "invoka",
    host="0.0.0.0",
    instructions=(
        "MCP server for INVOKA (invoka.com.ec), a credit-based electronic billing "
        "platform for Ecuador (SRI). "
        "Supports issuing: Invoices (01), Credit Notes (04), Retention Vouchers (07), "
        "and Remittance Guides (06). "
        "Company management: create, edit, upload digital signature (.p12), and logo. "
        "Credit management: check balance and history. "
        "Requires INVOKA_API_KEY environment variable. "
        "CRITICAL RULES: "
        "  · ambiente 1 = TESTING (free, unlimited — use for development). "
        "  · ambiente 2 = PRODUCTION (costs 1 credit per authorized document). "
        "  · Date format ALWAYS: YYYY/MM/DD with slashes. Example: '2025/07/30'. "
        "  · tipo_identificacion: 04=RUC, 05=Cedula, 06=Passport, "
        "    07=Final consumer (identificacion='9999999999999'). "
        "  · tipo_iva: 0=0%, 2=12%, 3=14%, 4=15%, 5=5%, 6=Not taxable, 7=Exempt. "
        "  · Totals and taxes are auto-calculated if not provided."
    ))

# ---------------------------------------------------------------------------
# Cliente HTTP reutilizable
# ---------------------------------------------------------------------------


def _build_headers() -> dict[str, str]:
    """Build auth headers for a specific account."""
    resolved = os.environ.get("INVOKA_API_KEY", "")
    if not resolved:
        raise ValueError(
            "api_key is required for this MCP. Pass it as a tool parameter."
        )
    return {
        "X-API-KEY": resolved,
        "Content-Type": "application/json",
    }



async def _request(
    method: str,
    path: str,
    *,    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None) -> dict | list | str:
    """Ejecuta una petición HTTP contra la API de INVOKA y devuelve la respuesta."""
    url = f"{INVOKA_BASE_URL}{path}"
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}

    logger.info("%s %s params=%s", method.upper(), url, params)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.request(
            method,
            url,
            headers=_build_headers(),
            params=params,
            json=body)
        logger.info("Respuesta HTTP %s", resp.status_code)

        if resp.status_code >= 400:
            return {
                "error": True,
                "status_code": resp.status_code,
                "detail": resp.text,
            }

        if not resp.text.strip():
            return {"ok": True, "status_code": resp.status_code}

        try:
            return resp.json()
        except Exception:
            return resp.text


def _build_emisor(
    ruc: str,
    nombre_comercial: str,
    codigo_establecimiento: str,
    codigo_puntoemision: str,
    direccion_matriz: str,
    direccion_establecimiento: str,
    fecha_emision: str,
    obligado_contabilidad: str = "SI",
    razon_social: str | None = None,
    secuencial: str | None = None,
    contribuyente_especial: str | None = None,
    agente_retencion: bool = False,
    gran_contribuyente: bool = False,
    regimen_rimpe: bool = False,
    regimen_rimpe_popular: bool = False,
    numero_resolucion: str | None = None) -> dict[str, Any]:
    """Construye el objeto emisor común a todos los documentos."""
    emisor: dict[str, Any] = {
        "ruc": ruc,
        "nombre_comercial": nombre_comercial,
        "codigo_establecimiento": codigo_establecimiento,
        "codigo_puntoemision": codigo_puntoemision,
        "direccion_matriz": direccion_matriz,
        "direccion_establecimiento": direccion_establecimiento,
        "obligado_contabilidad": obligado_contabilidad,
        "fecha_emision": fecha_emision,
        "agente_retencion": agente_retencion,
        "gran_contribuyente": gran_contribuyente,
        "regimen_rimpe": regimen_rimpe,
        "regimen_rimpe_popular": regimen_rimpe_popular,
    }
    if razon_social is not None:
        emisor["razon_social"] = razon_social
    if secuencial is not None:
        emisor["secuencial"] = secuencial
    if contribuyente_especial is not None:
        emisor["contribuyente_especial"] = contribuyente_especial
    if numero_resolucion is not None:
        emisor["numero_resolucion"] = numero_resolucion
    return emisor


# ═══════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN / PING
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def ping() -> str:
    """Verify INVOKA API connectivity and validate the configured API Key.

    Use this tool to check if INVOKA_API_KEY is valid and the service is reachable
    before attempting document emission.

    RETURNS:
      {"pong": true} if the key is valid and service is healthy.
    """
    result = await _request("POST", "/api/ping")
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# GESTIÓN DE EMPRESAS
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def crear_empresa(    ruc: str,
    razon_social: str,
    ncontribuyenteespecial: str | None = None,
    calificacionartesanal: str | None = None,
    exportador_habitual: bool = False,
    grancontribuyente: bool = False,
    agenteretencion: bool = False,
    contabilidad: bool = False,
    regimen_rimpe: bool = False,
    regimen_rimpe_popular: bool = False,
    numero_resolucion: str | None = None,
    smtp: bool = False,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    smtp_encryption: str | None = None,
    smtp_from_email: str | None = None,
    smtp_from_name: str | None = None) -> str:
    """⚠️ MUTATION — Register a new company in INVOKA for electronic document emission — POST /api/empresa/crear.

    REQUIRED PARAMETERS:
      ruc (str): Company RUC (13 digits). Example: "0912345678001"
      razon_social (str): Legal company name. Example: "Mi Empresa S.A."

    OPTIONAL PARAMETERS:
      ncontribuyenteespecial (str): Special taxpayer resolution number.
      calificacionartesanal (str): Artisan qualification number.
      exportador_habitual (bool, default=False): Regular exporter flag.
      grancontribuyente (bool, default=False): Large taxpayer flag.
      agenteretencion (bool, default=False): Withholding agent flag.
                                              If True, numero_resolucion is REQUIRED.
      contabilidad (bool, default=False): Required to maintain accounting records.
      regimen_rimpe (bool, default=False): RIMPE regime. Mutually exclusive with rimpe_popular.
      regimen_rimpe_popular (bool, default=False): RIMPE popular regime.
      numero_resolucion (str): Resolution number. REQUIRED when agenteretencion=True.
      smtp (bool, default=False): Enable custom email server for document delivery.
                                   If True, smtp_host, smtp_port, smtp_user,
                                   smtp_password, smtp_from_email are REQUIRED.
      smtp_host, smtp_port, smtp_user, smtp_password: SMTP server credentials.
      smtp_encryption (str): "tls" | "ssl" | None.
      smtp_from_email (str): Sender email address.
      smtp_from_name (str): Sender display name.

    RETURNS:
      Dict with company creation result and assigned company ID.
    """
    body: dict[str, Any] = {
        "ruc": ruc,
        "razon_social": razon_social,
        "exportador_habitual": exportador_habitual,
        "grancontribuyente": grancontribuyente,
        "agenteretencion": agenteretencion,
        "contabilidad": contabilidad,
        "regimen_rimpe": regimen_rimpe,
        "regimen_rimpe_popular": regimen_rimpe_popular,
        "smtp": smtp,
    }
    optionals = {
        "ncontribuyenteespecial": ncontribuyenteespecial,
        "calificacionartesanal": calificacionartesanal,
        "numero_resolucion": numero_resolucion,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "smtp_encryption": smtp_encryption,
        "smtp_from_email": smtp_from_email,
        "smtp_from_name": smtp_from_name,
    }
    for k, v in optionals.items():
        if v is not None:
            body[k] = v

    result = await _request("POST", "/api/empresa/crear", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def editar_empresa(    ruc: str,
    razon_social: str,
    ncontribuyenteespecial: str | None = None,
    calificacionartesanal: str | None = None,
    exportador_habitual: bool = False,
    grancontribuyente: bool = False,
    agenteretencion: bool = False,
    contabilidad: bool = False,
    regimen_rimpe: bool = False,
    regimen_rimpe_popular: bool = False,
    numero_resolucion: str | None = None,
    smtp: bool = False,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    smtp_encryption: str | None = None,
    smtp_from_email: str | None = None,
    smtp_from_name: str | None = None) -> str:
    """⚠️ MUTATION — Update an existing company's data in INVOKA — PUT /api/empresa/editar.

    Same fields and business rules as crear_empresa apply.

    REQUIRED PARAMETERS:
      ruc (str): RUC of the company to update (used as identifier). Example: "0912345678001"
      razon_social (str): Updated legal company name.

    OPTIONAL PARAMETERS:
      (Same optional fields as crear_empresa.)

    RETURNS:
      Dict with update result from INVOKA.
    """
    body: dict[str, Any] = {
        "ruc": ruc,
        "razon_social": razon_social,
        "exportador_habitual": exportador_habitual,
        "grancontribuyente": grancontribuyente,
        "agenteretencion": agenteretencion,
        "contabilidad": contabilidad,
        "regimen_rimpe": regimen_rimpe,
        "regimen_rimpe_popular": regimen_rimpe_popular,
        "smtp": smtp,
    }
    optionals = {
        "ncontribuyenteespecial": ncontribuyenteespecial,
        "calificacionartesanal": calificacionartesanal,
        "numero_resolucion": numero_resolucion,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "smtp_encryption": smtp_encryption,
        "smtp_from_email": smtp_from_email,
        "smtp_from_name": smtp_from_name,
    }
    for k, v in optionals.items():
        if v is not None:
            body[k] = v

    result = await _request("PUT", "/api/empresa/editar", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def subir_firma_electronica(    ruc: str,
    password: str,
    firma_base64: str) -> str:
    """⚠️ MUTATION — Upload the digital signature (.p12) for a company in INVOKA — POST /api/empresa/subirfirma.

    The digital signature is required to sign and emit electronic documents to the SRI.
    Must be provided as a Base64-encoded string.

    REQUIRED PARAMETERS:
      ruc (str): Company RUC (13 digits). Example: "0912345678001"
      password (str): Password of the .p12 file.
      firma_base64 (str): Content of the .p12 file encoded in Base64 (WITHOUT data: prefix).
                          Convert with: base64.b64encode(open('firma.p12','rb').read()).decode()

    RETURNS:
      Dict with upload result and signature validation status.
    """
    body: dict[str, Any] = {
        "ruc": ruc,
        "password": password,
        "firma_base64": firma_base64,
    }
    result = await _request("POST", "/api/empresa/subirfirma", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def subir_logo_empresa(    ruc: str,
    logo_base64: str) -> str:
    """⚠️ MUTATION — Upload a company logo to INVOKA — POST /api/empresa/subirlogo.

    The logo is printed on all electronic document PDFs (RIDE).
    Must be provided as a Base64-encoded string WITHOUT the data URI prefix.

    REQUIRED PARAMETERS:
      ruc (str): Company RUC (13 digits). Example: "0912345678001"
      logo_base64 (str): Image content (PNG, JPG, JPEG, max 2MB) encoded in Base64
                         WITHOUT "data:image/...;base64," prefix.
                         Convert with: base64.b64encode(open('logo.png','rb').read()).decode()

    RETURNS:
      Dict with upload result from INVOKA.
    """
    body: dict[str, Any] = {
        "ruc": ruc,
        "logo_base64": logo_base64,
    }
    result = await _request("POST", "/api/empresa/subirlogo", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# FACTURAS  –  /api/factura/emision
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def emitir_factura(    # Emisor
    emisor_ruc: str,
    emisor_nombre_comercial: str,
    emisor_codigo_establecimiento: str,
    emisor_codigo_puntoemision: str,
    emisor_direccion_matriz: str,
    emisor_direccion_establecimiento: str,
    emisor_fecha_emision: str,
    emisor_obligado_contabilidad: str,
    # Ambiente
    ambiente: int,
    # Comprador
    comprador_identificacion: str,
    comprador_tipo_identificacion: str,
    comprador_razon_social: str,
    comprador_direccion: str,
    # Items
    items: list[dict[str, Any]],
    # Opcionales emisor
    emisor_razon_social: str | None = None,
    emisor_secuencial: str | None = None,
    emisor_contribuyente_especial: str | None = None,
    emisor_agente_retencion: bool = False,
    emisor_gran_contribuyente: bool = False,
    emisor_regimen_rimpe: bool = False,
    emisor_regimen_rimpe_popular: bool = False,
    # Opcionales comprador
    comprador_telefono: str | None = None,
    comprador_celular: str | None = None,
    comprador_correo: str | None = None,
    # Opcionales factura
    pagos: list[dict[str, Any]] | None = None,
    informacion_adicional: list[dict[str, Any]] | None = None,
    guiaremision: str | None = None,
    placa: str | None = None) -> str:
    """⚠️ MUTATION — Issue an electronic invoice (Factura) to the SRI via INVOKA — POST /api/factura/emision.

    ⚠️ ENVIRONMENT: ambiente=1 = TESTING (FREE). ambiente=2 = PRODUCTION (costs 1 credit).
    Always use ambiente=1 during development and testing.

    REQUIRED PARAMETERS — ISSUER (emisor_*):
      emisor_ruc (str): 13-digit RUC. Example: "0912345678001"
      emisor_nombre_comercial (str): Commercial name of the issuer.
      emisor_codigo_establecimiento (str): Establishment code, 3 digits. Example: "001"
      emisor_codigo_puntoemision (str): Emission point code, 3 digits. Example: "001"
      emisor_direccion_matriz (str): Head office address.
      emisor_direccion_establecimiento (str): Establishment address.
      emisor_fecha_emision (str): Issue date in YYYY/MM/DD format. Example: "2025/07/30"
      emisor_obligado_contabilidad (str): Required accounting. Valid values: "SI" | "NO"
      ambiente (int): Environment. Valid values: 1=Testing (free), 2=Production (1 credit).

    REQUIRED PARAMETERS — BUYER (comprador_*):
      comprador_identificacion (str): Customer cedula/RUC/passport.
                                      For final consumer use "9999999999999".
      comprador_tipo_identificacion (str): ID type code.
                                           "04"=RUC, "05"=Cedula, "06"=Passport,
                                           "07"=Final consumer, "08"=Foreign ID.
      comprador_razon_social (str): Customer name or company name.
      comprador_direccion (str): Customer address.

    REQUIRED PARAMETERS — ITEMS (list[dict]):
      Each item in the 'items' list requires:
        descripcion (str): Product/service name.
        precio_unitario (float): Unit price without taxes.
        tipoproducto (int): Product type. Usually 1.
        cantidad (float): Quantity.
        tipo_iva (int): VAT type. 0=0%, 2=12%, 3=14%, 4=15%, 5=5%, 6=Not taxable, 7=Exempt.
      Optional per item:
        codigo_principal (str): Product code.
        descuento (float): Discount in monetary value.
        precio_total_sin_impuesto (float): Auto-calculated if omitted.
        detalles_adicionales (list): [{"nombre": "...", "detalle": "..."}]

    OPTIONAL PARAMETERS — ISSUER:
      emisor_razon_social (str): Legal company name (if different from commercial name).
      emisor_secuencial (str): 9-digit sequential number. Auto-assigned by INVOKA if omitted.
      emisor_contribuyente_especial (str): Special taxpayer resolution number.
      emisor_agente_retencion (bool, default=False): Withholding agent flag.
      emisor_gran_contribuyente (bool, default=False): Large taxpayer flag.
      emisor_regimen_rimpe (bool, default=False): RIMPE regime.
      emisor_regimen_rimpe_popular (bool, default=False): RIMPE popular regime.

    OPTIONAL PARAMETERS — BUYER:
      comprador_telefono (str): Customer phone.
      comprador_celular (str): Customer mobile.
      comprador_correo (str): Customer email.

    OPTIONAL PARAMETERS — INVOICE:
      pagos (list[dict]): Payment methods. Each: {"tipo": 20, "total": 11.50}.
                          tipo codes: 1=Cash, 16=Debit card, 19=Credit card, 20=Transfer.
      informacion_adicional (list[dict]): Additional info: [{"nombre": "...", "detalle": "..."}]
      guiaremision (str): Related remittance guide number.
      placa (str): Vehicle plate (for transport-related invoices).

    RETURNS:
      Dict with: id_comprobante, clave_acceso (49-digit SRI key),
      numero_autorizacion, estado, and ambiente.
    """
    emisor = _build_emisor(
        ruc=emisor_ruc,
        nombre_comercial=emisor_nombre_comercial,
        codigo_establecimiento=emisor_codigo_establecimiento,
        codigo_puntoemision=emisor_codigo_puntoemision,
        direccion_matriz=emisor_direccion_matriz,
        direccion_establecimiento=emisor_direccion_establecimiento,
        fecha_emision=emisor_fecha_emision,
        obligado_contabilidad=emisor_obligado_contabilidad,
        razon_social=emisor_razon_social,
        secuencial=emisor_secuencial,
        contribuyente_especial=emisor_contribuyente_especial,
        agente_retencion=emisor_agente_retencion,
        gran_contribuyente=emisor_gran_contribuyente,
        regimen_rimpe=emisor_regimen_rimpe,
        regimen_rimpe_popular=emisor_regimen_rimpe_popular)

    comprador: dict[str, Any] = {
        "identificacion": comprador_identificacion,
        "tipo_identificacion": comprador_tipo_identificacion,
        "razon_social": comprador_razon_social,
        "direccion": comprador_direccion,
    }
    for k, v in {
        "telefono": comprador_telefono,
        "celular": comprador_celular,
        "correo": comprador_correo,
    }.items():
        if v is not None:
            comprador[k] = v

    body: dict[str, Any] = {
        "emisor": emisor,
        "ambiente": ambiente,
        "comprador": comprador,
        "items": items,
    }
    if pagos:
        body["pagos"] = pagos
    if informacion_adicional:
        body["informacion_adicional"] = informacion_adicional
    if guiaremision is not None:
        body["guiaremision"] = guiaremision
    if placa is not None:
        body["placa"] = placa

    result = await _request("POST", "/api/factura/emision", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# NOTAS DE CRÉDITO  –  /api/credito/emision
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def emitir_nota_credito(    # Emisor
    emisor_ruc: str,
    emisor_nombre_comercial: str,
    emisor_codigo_establecimiento: str,
    emisor_codigo_puntoemision: str,
    emisor_direccion_matriz: str,
    emisor_direccion_establecimiento: str,
    emisor_fecha_emision: str,
    emisor_secuencial: str,
    # Ambiente
    ambiente: int,
    # Comprador
    comprador_tipo_identificacion: str,
    comprador_identificacion: str,
    comprador_razon_social: str,
    comprador_direccion: str,
    # Documento modificado
    codigo_documento_sustento: int,
    numero_documento_sustento: str,
    fecha_documento_sustento: str,
    motivo: str,
    # Items
    items: list[dict[str, Any]],
    # Opcionales emisor
    emisor_razon_social: str | None = None,
    emisor_obligado_contabilidad: str = "SI",
    emisor_contribuyente_especial: str | None = None,
    # Opcionales comprador
    comprador_telefono: str | None = None,
    comprador_celular: str | None = None,
    comprador_correo: str | None = None,
    # Opcionales documento
    anula_comprobante: str | None = None,
    informacion_adicional: list[dict[str, Any]] | None = None) -> str:
    """⚠️ MUTATION — Issue an electronic credit note (Nota de Crédito) to the SRI via INVOKA — POST /api/credito/emision.

    Use credit notes to cancel or partially correct a previously issued invoice.

    ⚠️ ENVIRONMENT: ambiente=1 = TESTING (FREE). ambiente=2 = PRODUCTION (costs 1 credit).

    REQUIRED PARAMETERS — ISSUER (emisor_*):
      emisor_ruc, emisor_nombre_comercial, emisor_codigo_establecimiento,
      emisor_codigo_puntoemision, emisor_direccion_matriz, emisor_direccion_establecimiento,
      emisor_fecha_emision (str, YYYY/MM/DD format).
      emisor_secuencial (str): 9-digit sequential number. Example: "000000001"
      ambiente (int): 1=Testing, 2=Production.

    REQUIRED PARAMETERS — ORIGINAL DOCUMENT (document being corrected):
      codigo_documento_sustento (int): Type of corrected document.
                                        1=Invoice, 4=Credit Note, 5=Debit Note.
      numero_documento_sustento (str): Document number, 15 digits without dashes.
      fecha_documento_sustento (str): Original document date in YYYY/MM/DD.
      motivo (str): Reason for issuing the credit note.

    REQUIRED PARAMETERS — BUYER (comprador_*):
      comprador_tipo_identificacion, comprador_identificacion,
      comprador_razon_social, comprador_direccion.

    REQUIRED PARAMETERS — ITEMS (list[dict]):
      Each item requires at minimum: descripcion, cantidad, precio_unitario.
      Optional per item: codigo_principal, descuento,
      tipo_iva (0=0%, 2=12%, 4=15%).

    OPTIONAL PARAMETERS:
      anula_comprobante (str): Set "SI" for full cancellation of the original invoice.
      informacion_adicional (list[dict]): [{"nombre": "...", "detalle": "..."}]
      emisor_razon_social, emisor_obligado_contabilidad (default="SI"),
      emisor_contribuyente_especial, comprador_telefono, comprador_celular, comprador_correo.

    RETURNS:
      Dict with: id_comprobante, clave_acceso, numero_autorizacion, estado.
    """
    emisor = _build_emisor(
        ruc=emisor_ruc,
        nombre_comercial=emisor_nombre_comercial,
        codigo_establecimiento=emisor_codigo_establecimiento,
        codigo_puntoemision=emisor_codigo_puntoemision,
        direccion_matriz=emisor_direccion_matriz,
        direccion_establecimiento=emisor_direccion_establecimiento,
        fecha_emision=emisor_fecha_emision,
        obligado_contabilidad=emisor_obligado_contabilidad,
        razon_social=emisor_razon_social,
        secuencial=emisor_secuencial,
        contribuyente_especial=emisor_contribuyente_especial)

    comprador: dict[str, Any] = {
        "tipo_identificacion": comprador_tipo_identificacion,
        "identificacion": comprador_identificacion,
        "razon_social": comprador_razon_social,
        "direccion": comprador_direccion,
    }
    for k, v in {
        "telefono": comprador_telefono,
        "celular": comprador_celular,
        "correo": comprador_correo,
    }.items():
        if v is not None:
            comprador[k] = v

    documento_modificado: dict[str, Any] = {
        "codigo_documento_sustento": codigo_documento_sustento,
        "numero_documento_sustento": numero_documento_sustento,
        "fecha_documento_sustento": fecha_documento_sustento,
        "motivo": motivo,
    }
    if anula_comprobante is not None:
        documento_modificado["anula_comprobante"] = anula_comprobante

    body: dict[str, Any] = {
        "emisor": emisor,
        "ambiente": ambiente,
        "comprador": comprador,
        "documento_modificado": documento_modificado,
        "items": items,
    }
    if informacion_adicional:
        body["informacion_adicional"] = informacion_adicional

    result = await _request("POST", "/api/credito/emision", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# GUÍAS DE REMISIÓN  –  /api/guia/emision
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def emitir_guia_remision(    # Emisor
    emisor_ruc: str,
    emisor_nombre_comercial: str,
    emisor_codigo_establecimiento: str,
    emisor_codigo_puntoemision: str,
    emisor_direccion_matriz: str,
    emisor_direccion_establecimiento: str,
    emisor_fecha_emision: str,
    emisor_secuencial: str,
    # Ambiente
    ambiente: int,
    # Transportista
    transportista_tipo_identificacion: str,
    transportista_identificacion: str,
    transportista_razon_social: str,
    # Destinatario
    destinatario_tipo_identificacion: str,
    destinatario_identificacion: str,
    destinatario_razon_social: str,
    destinatario_direccion: str,
    # Traslado
    traslado_direccion_destino: str,
    # Items
    items: list[dict[str, Any]],
    # Opcionales emisor
    emisor_razon_social: str | None = None,
    emisor_obligado_contabilidad: str = "SI",
    # Opcionales transportista
    transportista_placa: str | None = None,
    transportista_direccion: str | None = None,
    transportista_correo: str | None = None,
    # Opcionales destinatario
    destinatario_telefono: str | None = None,
    destinatario_celular: str | None = None,
    destinatario_correo: str | None = None,
    destinatario_nombre_sucursal: str | None = None,
    # Opcionales traslado
    traslado_fecha_inicio: str | None = None,
    traslado_fecha_fin: str | None = None,
    traslado_punto_partida: str | None = None,
    traslado_ruta: str | None = None,
    traslado_motivo: str | None = None,
    # Documento sustento
    doc_sustento_codigo: int | None = None,
    doc_sustento_numero: str | None = None,
    doc_sustento_fecha: str | None = None,
    doc_sustento_autorizacion: str | None = None,
    informacion_adicional: list[dict[str, Any]] | None = None) -> str:
    """⚠️ MUTATION — Issue an electronic remittance guide (Guía de Remisión) via INVOKA — POST /api/guia/emision.

    Use this tool to document the transport/transfer of goods between locations.

    ⚠️ ENVIRONMENT: ambiente=1 = TESTING (FREE). ambiente=2 = PRODUCTION (costs 1 credit).

    REQUIRED PARAMETERS — ISSUER:
      emisor_ruc, emisor_nombre_comercial, emisor_codigo_establecimiento,
      emisor_codigo_puntoemision, emisor_direccion_matriz, emisor_direccion_establecimiento,
      emisor_fecha_emision (YYYY/MM/DD), emisor_secuencial (9-digit sequential number).
      ambiente (int): 1=Testing, 2=Production.

    REQUIRED PARAMETERS — CARRIER (transportista_*):
      transportista_tipo_identificacion (str): "04"=RUC, "05"=Cedula, etc.
      transportista_identificacion (str): ID number.
      transportista_razon_social (str): Carrier name.

    REQUIRED PARAMETERS — RECIPIENT (destinatario_*):
      destinatario_tipo_identificacion, destinatario_identificacion,
      destinatario_razon_social, destinatario_direccion.

    REQUIRED PARAMETERS — TRANSPORT:
      traslado_direccion_destino (str): Destination address.

    REQUIRED PARAMETERS — ITEMS (list[dict]):
      Each item requires: codigo_principal, descripcion, cantidad.
      Optional: codigo_auxiliar, unidad_medida, detalles_adicionales.

    OPTIONAL PARAMETERS — CARRIER:
      transportista_placa (str): Vehicle plate.
      transportista_direccion, transportista_correo.

    OPTIONAL PARAMETERS — RECIPIENT:
      destinatario_telefono, destinatario_celular, destinatario_correo,
      destinatario_nombre_sucursal.

    OPTIONAL PARAMETERS — TRANSPORT:
      traslado_fecha_inicio, traslado_fecha_fin (YYYY/MM/DD): Transport date range.
      traslado_punto_partida, traslado_ruta, traslado_motivo.

    OPTIONAL PARAMETERS — SUPPORT DOCUMENT (doc that justifies the transport):
      doc_sustento_codigo (int): 1=Invoice, etc.
      doc_sustento_numero (str): Document number, 15 digits without dashes.
      doc_sustento_fecha (str): Date in YYYY/MM/DD.
      doc_sustento_autorizacion (str): SRI access key, 49 digits.

    RETURNS:
      Dict with: id_comprobante, clave_acceso, numero_autorizacion, estado.
    """
    emisor = _build_emisor(
        ruc=emisor_ruc,
        nombre_comercial=emisor_nombre_comercial,
        codigo_establecimiento=emisor_codigo_establecimiento,
        codigo_puntoemision=emisor_codigo_puntoemision,
        direccion_matriz=emisor_direccion_matriz,
        direccion_establecimiento=emisor_direccion_establecimiento,
        fecha_emision=emisor_fecha_emision,
        obligado_contabilidad=emisor_obligado_contabilidad,
        razon_social=emisor_razon_social,
        secuencial=emisor_secuencial)

    transportista: dict[str, Any] = {
        "tipo_identificacion": transportista_tipo_identificacion,
        "identificacion": transportista_identificacion,
        "razon_social": transportista_razon_social,
    }
    for k, v in {
        "placa": transportista_placa,
        "direccion": transportista_direccion,
        "correo": transportista_correo,
    }.items():
        if v is not None:
            transportista[k] = v

    destinatario: dict[str, Any] = {
        "tipo_identificacion": destinatario_tipo_identificacion,
        "identificacion": destinatario_identificacion,
        "razon_social": destinatario_razon_social,
        "direccion": destinatario_direccion,
    }
    for k, v in {
        "telefono": destinatario_telefono,
        "celular": destinatario_celular,
        "correo": destinatario_correo,
        "nombre_sucursal": destinatario_nombre_sucursal,
    }.items():
        if v is not None:
            destinatario[k] = v

    traslado: dict[str, Any] = {"direccion_destino": traslado_direccion_destino}
    for k, v in {
        "fecha_inicio_transporte": traslado_fecha_inicio,
        "fecha_fin_transporte": traslado_fecha_fin,
        "punto_partida": traslado_punto_partida,
        "ruta": traslado_ruta,
        "motivo_traslado": traslado_motivo,
    }.items():
        if v is not None:
            traslado[k] = v

    body: dict[str, Any] = {
        "emisor": emisor,
        "ambiente": ambiente,
        "transportista": transportista,
        "destinatario": destinatario,
        "traslado": traslado,
        "items": items,
    }

    # Documento sustento (opcional)
    if doc_sustento_numero:
        sustento: dict[str, Any] = {}
        if doc_sustento_codigo is not None:
            sustento["codigo_documento_sustento"] = doc_sustento_codigo
        sustento["numero_documento_sustento"] = doc_sustento_numero
        if doc_sustento_fecha:
            sustento["fecha_emision_documento_sustento"] = doc_sustento_fecha
        if doc_sustento_autorizacion:
            sustento["autorizacion_documento_sustento"] = doc_sustento_autorizacion
        body["documento_sustento"] = sustento

    if informacion_adicional:
        body["informacion_adicional"] = informacion_adicional

    result = await _request("POST", "/api/guia/emision", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# RETENCIONES  –  /api/retencion/emision
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def emitir_retencion(    # Emisor
    emisor_ruc: str,
    emisor_nombre_comercial: str,
    emisor_codigo_establecimiento: str,
    emisor_codigo_puntoemision: str,
    emisor_direccion_matriz: str,
    emisor_direccion_establecimiento: str,
    emisor_fecha_emision: str,
    emisor_secuencial: str,
    # Ambiente
    ambiente: int,
    # Proveedor (sujeto retenido)
    proveedor_tipo_identificacion: str,
    proveedor_identificacion: str,
    proveedor_razon_social: str,
    proveedor_direccion: str,
    # Sustento del documento
    sustento_codigo_sustento_tributario: str,
    sustento_codigo_documento: str,
    sustento_numero_documento: str,
    sustento_numero_autorizacion: str,
    sustento_fecha_documento: str,
    sustento_fecha_registro_contable: str,
    # Retenciones
    retenciones: list[dict[str, Any]],
    # Opcionales emisor
    emisor_razon_social: str | None = None,
    emisor_obligado_contabilidad: str = "SI",
    emisor_agente_retencion: bool = True,
    # Opcionales proveedor
    proveedor_telefono: str | None = None,
    proveedor_correo: str | None = None,
    # Opcionales sustento: items O gastos (no ambos)
    sustento_items: list[dict[str, Any]] | None = None,
    sustento_gastos: list[dict[str, Any]] | None = None,
    informacion_adicional: list[dict[str, Any]] | None = None) -> str:
    """⚠️ MUTATION — Issue an electronic retention voucher (Comprobante de Retención, code 07) via INVOKA — POST /api/retencion/emision.

    ⚠️ ENVIRONMENT: ambiente=1 = TESTING (FREE). ambiente=2 = PRODUCTION (costs 1 credit).
    ⚠️ The issuing company MUST be a withholding agent (emisor_agente_retencion=True).

    REQUIRED PARAMETERS — ISSUER:
      emisor_ruc, emisor_nombre_comercial, emisor_codigo_establecimiento,
      emisor_codigo_puntoemision, emisor_direccion_matriz, emisor_direccion_establecimiento,
      emisor_fecha_emision (YYYY/MM/DD), emisor_secuencial (9-digit sequential).
      ambiente (int): 1=Testing, 2=Production.

    REQUIRED PARAMETERS — SUPPLIER (proveedor_*, party being withheld from):
      proveedor_tipo_identificacion (str): "04"=RUC, "05"=Cedula, etc.
      proveedor_identificacion, proveedor_razon_social, proveedor_direccion.

    REQUIRED PARAMETERS — SOURCE DOCUMENT (sustento_*):
      sustento_codigo_sustento_tributario (str): Tax support code.
                                                  "01"=VAT tax credit, "02"=Cost or expense.
      sustento_codigo_documento (str): Source document type. "01"=Invoice, "03"=Purchase liquidation.
      sustento_numero_documento (str): Document number, 15 digits without dashes.
      sustento_numero_autorizacion (str): Authorization key (49 digits electronic, 10 physical).
      sustento_fecha_documento (str): Document date in YYYY/MM/DD.
      sustento_fecha_registro_contable (str): Accounting entry date in YYYY/MM/DD.
      sustento_items OR sustento_gastos (list[dict]): Use ONE, not both.
        · sustento_items: List of products. Each: {codigo_principal, descripcion,
                          tipo_iva, precio_unitario, cantidad}.
        · sustento_gastos: List of subtotals by type. Each: {descripcion,
                           subtotal_iva, subtotal_siniva, subtotal_ivacero, tipo_iva}.

    REQUIRED PARAMETERS — RETENTIONS (list[dict], minimum 1):
      Each retention object:
        base_imponible (float): ⚠️ TAXABLE BASE AMOUNT (Base Imponible). DO NOT confuse with Total.
        codigoimpuesto (int): 1=Income tax (Renta), 2=VAT (IVA), 6=ISD.
        codigo_retencion (str): SRI retention code. Example: "303", "304", "10", "20".
        porcentaje_retencion (float): Retention percentage.
        valor_retenido (float): Calculated retained amount.

    OPTIONAL PARAMETERS:
      emisor_razon_social, emisor_obligado_contabilidad (default="SI"),
      emisor_agente_retencion (bool, default=True).
      proveedor_telefono, proveedor_correo.
      informacion_adicional (list[dict]): [{"nombre": "...", "detalle": "..."}]

    RETURNS:
      Dict with: id_comprobante, clave_acceso, numero_autorizacion, estado.
    """
    emisor = _build_emisor(
        ruc=emisor_ruc,
        nombre_comercial=emisor_nombre_comercial,
        codigo_establecimiento=emisor_codigo_establecimiento,
        codigo_puntoemision=emisor_codigo_puntoemision,
        direccion_matriz=emisor_direccion_matriz,
        direccion_establecimiento=emisor_direccion_establecimiento,
        fecha_emision=emisor_fecha_emision,
        obligado_contabilidad=emisor_obligado_contabilidad,
        razon_social=emisor_razon_social,
        secuencial=emisor_secuencial,
        agente_retencion=emisor_agente_retencion)

    proveedor: dict[str, Any] = {
        "tipo_identificacion": proveedor_tipo_identificacion,
        "identificacion": proveedor_identificacion,
        "razon_social": proveedor_razon_social,
        "direccion": proveedor_direccion,
    }
    for k, v in {
        "telefono": proveedor_telefono,
        "correo": proveedor_correo,
    }.items():
        if v is not None:
            proveedor[k] = v

    sustento: dict[str, Any] = {
        "codigo_sustento_tributario": sustento_codigo_sustento_tributario,
        "codigo_documento_sustento": sustento_codigo_documento,
        "numero_documento_sustento": sustento_numero_documento,
        "numero_autorizacion": sustento_numero_autorizacion,
        "fecha_documento_sustento": sustento_fecha_documento,
        "fecha_registro_contable": sustento_fecha_registro_contable,
    }
    if sustento_items:
        sustento["items"] = sustento_items
    elif sustento_gastos:
        sustento["gastos"] = sustento_gastos

    body: dict[str, Any] = {
        "emisor": emisor,
        "ambiente": ambiente,
        "codigoDoc": "07",
        "proveedor": proveedor,
        "sustento": sustento,
        "retenciones": retenciones,
    }
    if informacion_adicional:
        body["informacion_adicional"] = informacion_adicional

    result = await _request("POST", "/api/retencion/emision", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# CRÉDITOS  –  /api/creditos/
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def consultar_saldo_creditos() -> str:
    """Check the available credit balance in the INVOKA account — GET /api/creditos/saldo.

    Use this tool before emitting documents in production (ambiente=2) to verify
    that sufficient credits are available. Credits are only deducted when the SRI
    authorizes a document in production.

    RETURNS:
      Dict with: creditos_disponibles (int), estado_saldo.
      estado_saldo values: "suficiente" | "bajo" | "agotado"
    """
    result = await _request("GET", "/api/creditos/saldo")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def consultar_historial_creditos(    limit: int | None = None,
    page: int | None = None,
    tipo: str | None = None,
    ambiente: str | None = None) -> str:
    """Retrieve credit consumption and recharge history for the INVOKA account — GET /api/creditos/historial.

    Use this tool to audit credit usage, track which documents consumed credits,
    or confirm credit recharges.

    OPTIONAL PARAMETERS:
      limit (int, default=20, max=100): Maximum number of records to return.
      page (int): Page number for pagination. Example: 2
      tipo (str): Filter by operation type.
                  Valid values: "consumo" | "recarga" | "rollback"
      ambiente (str): Filter by environment.
                      Valid values: "1"=Testing | "2"=Production.

    RETURNS:
      Dict with list of credit history entries: fecha, tipo, cantidad, descripcion.
    """
    result = await _request(
        "GET",
        "/api/creditos/historial",
        params={
            "limit": limit,
            "page": page,
            "tipo": tipo,
            "ambiente": ambiente,
        })
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# REPROCESAMIENTO  –  /api/consultaprocesar
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def reprocesar_comprobante(    ruc: str,
    id_comprobante: int,
    clave_acceso: str) -> str:
    """Re-query and reprocess an INVOKA voucher stuck in an intermediate state — POST /api/consultaprocesar.

    Use this tool when a document was registered but not fully processed
    (e.g. connection dropped while sending to the SRI). Do NOT use as a
    first-emission tool — only for recovery of existing stuck vouchers.

    REQUIRED PARAMETERS:
      ruc (str): RUC of the issuing company. 13 digits. Example: "0912345678001"
      id_comprobante (int): Internal INVOKA voucher ID returned during emission.
                            This is the 'id_comprobante' field in the emission response.
      clave_acceso (str): SRI access key of the voucher, 49 digits.

    RETURNS:
      Dict with current voucher status and SRI authorization result.
    """
    body: dict[str, Any] = {
        "ruc": ruc,
        "idcomprobanteinvoka": id_comprobante,
        "claveacceso": clave_acceso,
    }
    result = await _request("POST", "/api/consultaprocesar", body=body)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import uvicorn
    import os


    port = int(os.getenv("MCP_PORT", 8000))
    transport_mode = os.getenv("MCP_TRANSPORT_MODE", "sse").lower()
    print(f"Starting MCP Server on http://0.0.0.0:{port}/mcp ({transport_mode})")
    if transport_mode == "sse":
        app = mcp.sse_app()
    elif transport_mode == "http_stream":
        app = mcp.streamable_http_app()
    else:
        raise ValueError(f"Unknown transport mode: {transport_mode}")
    uvicorn.run(app, host="0.0.0.0", port=port)
