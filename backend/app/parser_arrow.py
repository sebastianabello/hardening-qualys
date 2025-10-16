"""
Parser optimizado con fallback robusto.
Usa PyArrow cuando es posible, pero con fallback automático al parser estándar.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator, Tuple, List, Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)

AJUSTADA_TOKENS = ("AJUSTA", "AJUSTADA", "AJU")

try:
    import pyarrow.csv as pa_csv
    import pyarrow as pa
    import pandas as pd
    PYARROW_AVAILABLE = True
    logger.info("✅ PyArrow y Pandas disponibles - Parser optimizado activo")
except ImportError as e:
    PYARROW_AVAILABLE = False
    logger.warning(f"⚠️ PyArrow/Pandas no disponible: {e} - Usando parser estándar")


def _norm(s: str) -> str:
    return s.strip().strip('"').strip("'")


def _is_t1_marker(s: str) -> bool:
    return _norm(s).upper().startswith("CONTROL STATISTICS")


def _is_t2_marker(s: str) -> bool:
    return _norm(s).upper() == "RESULTS"


def _is_host_marker(s: str) -> bool:
    return _norm(s).upper().startswith("HOST STATISTICS")


def _is_any_marker(s: str) -> bool:
    s = _norm(s)
    return _is_t1_marker(s) or _is_t2_marker(s) or _is_host_marker(s) or s.upper() in ("ASSET TAGS", "SUMMARY")


def _extract_os(head_text: str) -> Optional[str]:
    pats = [
        r"CIS\s+Benchmark\s+for\s+(.+?)\s+v\d",
        r"CIS\s+(.+?)\s+Benchmark\s+v\d",
        r"CIS\s+Benchmark\s+for\s+(.+?)\s+version\s+\d",
        r"CIS\s+(.+?)\s+Benchmark\s+version\s+\d",
    ]
    for pat in pats:
        m = re.search(pat, head_text, flags=re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(1).strip())
    return None


def _detect_head(path: Path, empresas: List[str], nombre_defecto: str) -> tuple[bool, str, Optional[str]]:
    es_ajustada = False
    cliente = nombre_defecto
    os_name: Optional[str] = None
    
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        head = []
        for _ in range(10):
            ln = f.readline()
            if not ln:
                break
            head.append(ln)
        head_text = " ".join(head)
        es_ajustada = any(tok in head_text.upper() for tok in AJUSTADA_TOKENS)
        low = head_text.lower()
        for e in empresas:
            if e.lower() in low:
                cliente = e
                break
        os_name = _extract_os(head_text)
    
    return es_ajustada, cliente, os_name


def _detect_delimiter(header_line: str) -> str:
    return ";" if header_line.count(";") > header_line.count(",") else ","


def stream_tables_arrow(
    path: Path, 
    empresas: List[str], 
    nombre_defecto: str
) -> Iterator[Tuple[str, bool, Dict[str, str], List[str], Optional[str]]]:
    """
    Parser optimizado con fallback automático robusto.
    Intenta usar PyArrow/Pandas, pero si falla, usa el parser estándar.
    """
    file_size_mb = path.stat().st_size / 1024 / 1024
    
    # Para archivos muy grandes o si PyArrow no está disponible, usar parser estándar directamente
    if not PYARROW_AVAILABLE or file_size_mb > 1000:  # >1GB usar siempre parser estándar
        logger.info(f"📄 Usando parser estándar para {path.name} ({file_size_mb:.1f} MB)")
        from .parser_stream import stream_tables
        yield from stream_tables(path, empresas, nombre_defecto)
        return
    
    logger.info(f"🚀 Intentando PyArrow para {path.name} ({file_size_mb:.1f} MB)")
    
    try:
        # Intentar procesamiento optimizado con PyArrow/Pandas
        yield from _stream_with_pandas(path, empresas, nombre_defecto, file_size_mb)
    except Exception as e:
        logger.warning(f"⚠️ Error en PyArrow para {path.name}: {e}, usando parser estándar")
        # Fallback automático al parser estándar
        from .parser_stream import stream_tables
        yield from stream_tables(path, empresas, nombre_defecto)


def _stream_with_pandas(
    path: Path,
    empresas: List[str],
    nombre_defecto: str,
    file_size_mb: float
) -> Iterator[Tuple[str, bool, Dict[str, str], List[str], Optional[str]]]:
    """
    Procesamiento optimizado usando Pandas para archivos medianos (<1GB).
    Mucho más robusto que PyArrow directo.
    """
    es_ajustada, cliente, os_name = _detect_head(path, empresas, nombre_defecto)
    
    # Leer archivo línea por línea para encontrar secciones
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        current_section = None
        section_lines = []
        
        for line_num, line in enumerate(f, 1):
            line_stripped = _norm(line)
            
            if _is_any_marker(line_stripped):
                # Procesar sección anterior
                if current_section and section_lines:
                    try:
                        yield from _process_section_pandas(
                            section_lines, current_section, cliente, es_ajustada, os_name
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Error procesando sección {current_section[:20]}: {e}")
                        # Continuar con la siguiente sección en lugar de fallar
                
                # Iniciar nueva sección
                current_section = line_stripped
                section_lines = []
                
            elif current_section:
                section_lines.append(line)
                
                # Procesar por chunks para archivos medianos (cada 50k líneas)
                if len(section_lines) > 50000:
                    try:
                        yield from _process_section_pandas(
                            section_lines, current_section, cliente, es_ajustada, os_name
                        )
                        section_lines = []  # Limpiar buffer
                    except Exception as e:
                        logger.warning(f"⚠️ Error en chunk de sección {current_section[:20]}: {e}")
                        section_lines = []  # Limpiar y continuar
        
        # Procesar última sección
        if current_section and section_lines:
            try:
                yield from _process_section_pandas(
                    section_lines, current_section, cliente, es_ajustada, os_name
                )
            except Exception as e:
                logger.warning(f"⚠️ Error en última sección {current_section[:20]}: {e}")


def _process_section_pandas(
    lines: List[str],
    marker: str,
    cliente: str,
    es_ajustada: bool,
    os_name: Optional[str]
) -> Iterator[Tuple[str, bool, Dict[str, str], List[str], Optional[str]]]:
    """
    Procesa una sección usando Pandas (más robusto que PyArrow directo).
    """
    if not lines or len(lines) < 2:  # Necesita al menos header + 1 fila
        return
    
    is_t1 = _is_t1_marker(marker)
    is_t2 = _is_t2_marker(marker)
    
    if not (is_t1 or is_t2):
        return  # Ignorar otras secciones
    
    try:
        # Detectar delimitador del header
        header_line = lines[0]
        delim = _detect_delimiter(header_line)
        
        # Crear CSV temporal en memoria
        from io import StringIO
        csv_data = StringIO("".join(lines))
        
        # Leer con Pandas (más robusto que PyArrow directo)
        df = pd.read_csv(
            csv_data,
            delimiter=delim,
            dtype=str,  # Todo como string para evitar problemas de tipos
            na_filter=False,  # No convertir strings a NaN
            encoding='utf-8',
            on_bad_lines='skip',  # Saltar líneas problemáticas
            low_memory=False
        )
        
        if df.empty:
            return
        
        # Agregar columna Cliente si no existe
        if "Cliente" not in df.columns:
            df["Cliente"] = cliente
        else:
            df["Cliente"] = cliente  # Sobrescribir con el cliente detectado
        
        # Obtener columnas finales
        cols = df.columns.tolist()
        
        # Convertir a diccionarios y generar filas
        rows_processed = 0
        for _, row in df.iterrows():
            row_dict = {}
            for col in df.columns:
                value = row[col]
                # Manejar valores NaN o None
                if pd.isna(value) or value is None:
                    row_dict[col] = ""
                else:
                    row_dict[col] = str(value).strip()
            
            yield ("t1" if is_t1 else "t2", es_ajustada, row_dict, cols, os_name)
            rows_processed += 1
        
        if rows_processed > 0:
            logger.info(f"   ✅ Pandas procesó {rows_processed:,} filas de {marker[:30]}")
    
    except Exception as e:
        logger.warning(f"⚠️ Error en Pandas para sección {marker[:20]}: {e}")
        # No re-lanzar el error, simplemente continuar
        return
