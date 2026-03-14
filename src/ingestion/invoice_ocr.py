# =============================================================================
# src/ingestion/invoice_ocr.py
# Extraccion de datos de facturas electricas con Claude API
# Version: 1.0
#
# Soporta:
#   - PDF multipagina (una factura en varias paginas)
#   - Varias imagenes (fotos de cada pagina de una factura)
#   - Cualquier comercializadora y cualquier idioma
#
# Logica de precios:
#   - Si solo hay un precio de energia -> aplica igual a P1, P2 y P3
#   - Si solo hay un precio de potencia -> aplica igual a P1 y P2
# =============================================================================

import os
import io
import json
import base64
from pathlib import Path
from typing import Optional

import anthropic

import sys
sys.path.append('../..')
from src.models.internal_data_model import (
    ElectricityAnalysis,
    ClientProfile,
    ContractInfo,
    ContractedPowers,
    ClientType,
    ContractType,
    DataSource,
)


# =============================================================================
# PROMPT PRINCIPAL
# =============================================================================

EXTRACTION_PROMPT = """Eres un experto en facturas electricas espanolas. 
Analiza esta factura electrica y extrae TODOS los datos que encuentres.

Devuelve UNICAMENTE un JSON valido con esta estructura exacta, sin texto adicional:

{
  "contrato": {
    "cups": null,
    "nombre_titular": null,
    "direccion_suministro": null,
    "comercializadora": null,
    "distribuidora": null,
    "tipo_tarifa": null,
    "numero_contrato": null,
    "numero_factura": null,
    "fecha_emision": null,
    "fecha_fin_contrato": null,
    "potencia_contratada_p1_kw": null,
    "potencia_contratada_p2_kw": null
  },
  "periodo": {
    "fecha_inicio": null,
    "fecha_fin": null,
    "dias_facturados": null,
    "fecha_cobro": null
  },
  "consumo": {
    "total_kwh": null,
    "p1_punta_kwh": null,
    "p2_llano_kwh": null,
    "p3_valle_kwh": null,
    "potencia_maxima_demandada_p1_kw": null,
    "potencia_maxima_demandada_p2_kw": null
  },
  "precios_energia": {
    "precio_p1_eur_kwh": null,
    "precio_p2_eur_kwh": null,
    "precio_p3_eur_kwh": null,
    "precio_unico": false
  },
  "precios_potencia": {
    "precio_p1_eur_kw_dia": null,
    "precio_p2_eur_kw_dia": null,
    "precio_unico": false
  },
  "importes": {
    "termino_fijo_total_eur": null,
    "termino_fijo_p1_eur": null,
    "termino_fijo_p2_eur": null,
    "energia_total_eur": null,
    "energia_p1_eur": null,
    "energia_p2_eur": null,
    "energia_p3_eur": null,
    "servicios_adicionales_total_eur": null,
    "servicios_adicionales_detalle": [],
    "otros_conceptos_total_eur": null,
    "bono_social_eur": null,
    "alquiler_contador_eur": null,
    "impuestos_total_eur": null,
    "impuesto_electrico_eur": null,
    "impuesto_electrico_pct": null,
    "iva_eur": null,
    "iva_pct": null,
    "total_factura_eur": null
  },
  "peajes": {
    "peaje_potencia_eur": null,
    "peaje_energia_eur": null,
    "cuota_comercializacion_eur": null
  },
  "excesos_potencia": {
    "hay_excesos": false,
    "exceso_p1_eur": null,
    "exceso_p2_eur": null
  },
  "metadatos": {
    "idioma_factura": null,
    "paginas_procesadas": null,
    "confianza_extraccion": null,
    "campos_no_encontrados": [],
    "observaciones": null
  }
}

REGLAS IMPORTANTES:
1. Si solo encuentras UN precio de energia, pon ese mismo valor en precio_p1, precio_p2 y precio_p3, y pon "precio_unico": true
2. Si solo encuentras UN precio de potencia, pon ese mismo valor en precio_p1 y precio_p2, y pon "precio_unico": true
3. Las fechas en formato DD/MM/YYYY
4. Los importes en euros como numero decimal (ej: 20.62)
5. Si un campo no existe en la factura, pon null
6. En "campos_no_encontrados" lista los campos que no pudiste encontrar
7. En "confianza_extraccion" pon un valor del 1 al 10 segun lo bien que hayas podido leer la factura
8. La factura puede estar en cualquier idioma (castellano, catalan, euskera...)
9. NO inventes datos — si no lo ves claramente, pon null
"""


# =============================================================================
# CONVERTIR PDF A IMAGENES BASE64
# =============================================================================

def pdf_to_images_base64(pdf_path: str) -> list:
    """
    Convierte un PDF multipagina a lista de imagenes en base64.
    Requiere: pip install pdf2image pillow
    """
    try:
        from pdf2image import convert_from_path
        import PIL.Image

        print(f"  Convirtiendo PDF a imagenes: {pdf_path}")
        imagenes = convert_from_path(pdf_path, dpi=200)

        imagenes_b64 = []
        for i, img in enumerate(imagenes):
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            b64 = base64.standard_b64encode(buffer.getvalue()).decode('utf-8')
            imagenes_b64.append({
                'pagina': i + 1,
                'base64': b64,
                'media_type': 'image/png'
            })
            print(f"  Pagina {i+1} convertida")

        return imagenes_b64

    except ImportError:
        raise ImportError(
            "Instala las dependencias: pip install pdf2image pillow\n"
            "Y en Linux: sudo apt-get install poppler-utils"
        )


def images_to_base64(image_paths: list) -> list:
    """
    Convierte una lista de imagenes (JPG/PNG) a base64.
    """
    imagenes_b64 = []
    for i, path in enumerate(image_paths):
        with open(path, 'rb') as f:
            data = f.read()
        b64 = base64.standard_b64encode(data).decode('utf-8')

        # Detectar tipo de imagen
        ext = Path(path).suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.webp': 'image/webp',
        }
        media_type = media_type_map.get(ext, 'image/jpeg')

        imagenes_b64.append({
            'pagina': i + 1,
            'base64': b64,
            'media_type': media_type
        })
        print(f"  Imagen {i+1} cargada: {path}")

    return imagenes_b64


# =============================================================================
# LLAMADA A LA API DE CLAUDE
# =============================================================================

def extract_with_claude(imagenes_b64: list, api_key: str) -> dict:
    """
    Envia todas las imagenes de la factura a Claude en una sola llamada
    y devuelve el JSON con todos los datos extraidos.

    Args:
        imagenes_b64: Lista de imagenes en base64
        api_key:      API key de Anthropic

    Returns:
        Diccionario con todos los datos de la factura
    """
    client = anthropic.Anthropic(api_key=api_key)

    # Construir el contenido del mensaje con todas las imagenes
    content = []

    # Añadir todas las imagenes
    for img in imagenes_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img['media_type'],
                "data": img['base64'],
            }
        })

    # Añadir el prompt al final
    content.append({
        "type": "text",
        "text": EXTRACTION_PROMPT
    })

    print(f"  Enviando {len(imagenes_b64)} imagen(es) a Claude...")

    response = client.messages.create(
        model     = "claude-sonnet-4-20250514",
        max_tokens= 4096,
        messages  = [{"role": "user", "content": content}]
    )

    # Extraer el texto de la respuesta
    texto = response.content[0].text.strip()

    # Limpiar posibles marcadores de codigo
    if texto.startswith('```json'):
        texto = texto[7:]
    if texto.startswith('```'):
        texto = texto[3:]
    if texto.endswith('```'):
        texto = texto[:-3]
    texto = texto.strip()

    # Parsear JSON
    datos = json.loads(texto)

    print(f"  Extraccion completada — Confianza: {datos.get('metadatos',{}).get('confianza_extraccion','?')}/10")

    return datos


# =============================================================================
# VALIDACION DE DATOS EXTRAIDOS
# =============================================================================

def validate_extracted_data(datos: dict) -> dict:
    """
    Valida y corrige los datos extraidos por Claude.
    Aplica las reglas de precios unicos y verifica coherencia.
    """
    avisos = []

    # Validar precios de energia
    pe = datos.get('precios_energia', {})
    if pe:
        p1 = pe.get('precio_p1_eur_kwh')
        p2 = pe.get('precio_p2_eur_kwh')
        p3 = pe.get('precio_p3_eur_kwh')

        # Si solo hay P1 -> aplicar a todos
        if p1 and not p2 and not p3:
            datos['precios_energia']['precio_p2_eur_kwh'] = p1
            datos['precios_energia']['precio_p3_eur_kwh'] = p1
            datos['precios_energia']['precio_unico'] = True
            avisos.append(f"Precio energia unico detectado: {p1} €/kWh para P1, P2 y P3")

        # Si hay P1 y P2 pero no P3 -> P3 = P2 (valle = llano en algunas tarifas)
        elif p1 and p2 and not p3:
            datos['precios_energia']['precio_p3_eur_kwh'] = p2
            avisos.append(f"Precio P3 asignado igual a P2: {p2} €/kWh")

    # Validar precios de potencia
    pp = datos.get('precios_potencia', {})
    if pp:
        pot_p1 = pp.get('precio_p1_eur_kw_dia')
        pot_p2 = pp.get('precio_p2_eur_kw_dia')

        if pot_p1 and not pot_p2:
            datos['precios_potencia']['precio_p2_eur_kw_dia'] = pot_p1
            datos['precios_potencia']['precio_unico'] = True
            avisos.append(f"Precio potencia unico detectado: {pot_p1} €/kW/dia para P1 y P2")

    # Validar CUPS
    cups = datos.get('contrato', {}).get('cups', '')
    if cups and not cups.startswith('ES'):
        avisos.append(f"CUPS con formato inusual: {cups}")

    # Validar total factura
    total = datos.get('importes', {}).get('total_factura_eur')
    if total and total <= 0:
        avisos.append(f"Total factura inusual: {total} EUR")

    # Validar dias facturados
    dias = datos.get('periodo', {}).get('dias_facturados')
    if dias and (dias < 20 or dias > 45):
        avisos.append(f"Dias facturados inusuales: {dias}")

    if avisos:
        print("  Avisos de validacion:")
        for a in avisos:
            print(f"    - {a}")

    datos['_avisos_validacion'] = avisos
    return datos


# =============================================================================
# CONSTRUIR ContractInfo DESDE LOS DATOS EXTRAIDOS
# =============================================================================

def build_contract_info(datos: dict) -> Optional[ContractInfo]:
    """
    Construye el objeto ContractInfo del modelo interno
    a partir de los datos extraidos de la factura.
    """
    try:
        contrato = datos.get('contrato', {})

        p1_kw = contrato.get('potencia_contratada_p1_kw') or 0.0
        p2_kw = contrato.get('potencia_contratada_p2_kw') or p1_kw

        return ContractInfo(
            cups             = contrato.get('cups'),
            distributor      = contrato.get('distribuidora'),
            marketer         = contrato.get('comercializadora'),
            contracted_powers= ContractedPowers(p1=float(p1_kw), p2=float(p2_kw)),
            meter_rental     = datos.get('importes', {}).get('alquiler_contador_eur'),
        )
    except Exception as e:
        print(f"  Advertencia: no se pudo construir ContractInfo: {e}")
        return None


# =============================================================================
# FUNCION PRINCIPAL — PDF
# =============================================================================

def extract_from_pdf(
    pdf_path:  str,
    api_key:   str,
    analysis:  ElectricityAnalysis = None,
) -> dict:
    """
    Extrae datos de una factura en PDF (una o varias paginas).

    Args:
        pdf_path: Ruta al archivo PDF
        api_key:  API key de Anthropic
        analysis: ElectricityAnalysis existente (opcional, para actualizar el contrato)

    Returns:
        Diccionario con todos los datos extraidos y validados
    """
    print(f"Iniciando extraccion OCR desde PDF: {pdf_path}")

    # 1. Convertir PDF a imagenes
    imagenes = pdf_to_images_base64(pdf_path)
    print(f"  {len(imagenes)} paginas detectadas")

    # 2. Extraer datos con Claude
    datos = extract_with_claude(imagenes, api_key)

    # 3. Validar datos
    datos = validate_extracted_data(datos)

    # 4. Actualizar el analysis si se pasa
    if analysis is not None:
        contract_info = build_contract_info(datos)
        if contract_info:
            analysis.contract = contract_info
            analysis.data_source = DataSource.OCR
            print("  ContractInfo actualizado en ElectricityAnalysis")

    print("Extraccion OCR completada.")
    return datos


# =============================================================================
# FUNCION PRINCIPAL — IMAGENES
# =============================================================================

def extract_from_images(
    image_paths: list,
    api_key:     str,
    analysis:    ElectricityAnalysis = None,
) -> dict:
    """
    Extrae datos de una factura subida como varias fotos/imagenes.

    Args:
        image_paths: Lista de rutas a las imagenes (JPG, PNG...)
        api_key:     API key de Anthropic
        analysis:    ElectricityAnalysis existente (opcional)

    Returns:
        Diccionario con todos los datos extraidos y validados
    """
    print(f"Iniciando extraccion OCR desde {len(image_paths)} imagen(es)")

    # 1. Cargar imagenes en base64
    imagenes = images_to_base64(image_paths)

    # 2. Extraer datos con Claude
    datos = extract_with_claude(imagenes, api_key)

    # 3. Validar datos
    datos = validate_extracted_data(datos)

    # 4. Actualizar el analysis si se pasa
    if analysis is not None:
        contract_info = build_contract_info(datos)
        if contract_info:
            analysis.contract = contract_info
            analysis.data_source = DataSource.OCR
            print("  ContractInfo actualizado en ElectricityAnalysis")

    print("Extraccion OCR completada.")
    return datos


# =============================================================================
# FUNCION DE DETECCION AUTOMATICA
# =============================================================================

def extract_from_files(
    filepaths:  list,
    api_key:    str,
    analysis:   ElectricityAnalysis = None,
) -> dict:
    """
    Detecta automaticamente si los archivos son PDF o imagenes
    y llama a la funcion correcta.

    Args:
        filepaths: Lista de rutas (puede ser un PDF o varias imagenes)
        api_key:   API key de Anthropic
        analysis:  ElectricityAnalysis existente (opcional)

    Returns:
        Diccionario con todos los datos extraidos
    """
    if not filepaths:
        raise ValueError("No se han proporcionado archivos.")

    # Detectar si es PDF o imagenes
    extensiones_imagen = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}
    extensiones_pdf    = {'.pdf'}

    ext_primer = Path(filepaths[0]).suffix.lower()

    if ext_primer in extensiones_pdf:
        if len(filepaths) > 1:
            print("Advertencia: se han proporcionado varios PDFs. Se procesara solo el primero.")
        return extract_from_pdf(filepaths[0], api_key, analysis)

    elif ext_primer in extensiones_imagen:
        return extract_from_images(filepaths, api_key, analysis)

    else:
        raise ValueError(
            f"Formato no soportado: {ext_primer}. "
            f"Formatos validos: PDF, JPG, PNG, WEBP"
        )
