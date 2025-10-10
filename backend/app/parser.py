from __future__ import annotations
import csv, re, sys
import io
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# Palabras para detectar "ajustada" (cabecera o primeras líneas)
AJUSTADA_TOKENS = ("AJUSTA", "AJUSTADA", "AJU")

try:
    csv.field_size_limit(10 * 1024 * 1024)
except Exception:
    csv.field_size_limit(min(sys.maxsize, 2_147_483_647))

def _norm(s: str) -> str:
    return s.strip().strip('"').strip("'")

def _is_marker(line: str, target: str) -> bool:
    return _norm(line).upper() == target.upper()

def _is_t1_marker(s: str) -> bool:
    s = _norm(s).upper()
    return s.startswith("CONTROL STATISTICS")

def _is_t2_marker(s: str) -> bool:
    s = _norm(s).upper()
    return s == "RESULTS"

def _is_host_marker(s: str) -> bool:
    s = _norm(s).upper()
    return s.startswith("HOST STATISTICS")

def _is_any_marker(s: str) -> bool:
    s = _norm(s)
    return _is_t1_marker(s) or _is_t2_marker(s) or _is_host_marker(s) or s.upper() in ("ASSET TAGS", "SUMMARY")

def _detect_delimiter(header_line: str) -> str:
    # El header suele venir con comas o punto y coma
    return ";" if header_line.count(";") > header_line.count(",") else ","

def detect_ajustada(lines: List[str]) -> bool:
    head = " ".join(lines[:5]).upper()
    return any(tok in head for tok in AJUSTADA_TOKENS)

def detect_cliente(lines: List[str], empresas: List[str], nombre_defecto: str) -> str:
    head = " ".join(lines[:5]).lower()
    for e in empresas:
        if e.lower() in head:
            return e
    return nombre_defecto

def _extract_table(lines: List[str], marker: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Busca una línea cuyo contenido normalizado sea `marker`, toma la
    siguiente línea no vacía como encabezado, y luego filas hasta línea vacía
    o próximo marcador conocido.
    Devuelve (rows, columns)
    """
    n = len(lines)
    start_idx = None
    for i in range(n):
        if _is_marker(lines[i], marker):
            start_idx = i
            break
    if start_idx is None:
        return [], []

    # Header = próxima línea no vacía
    hdr_idx = None
    for j in range(start_idx + 1, n):
        if lines[j].strip():
            hdr_idx = j
            break
    if hdr_idx is None:
        return [], []

    delim = _detect_delimiter(lines[hdr_idx])
    reader = csv.reader(io.StringIO(lines[hdr_idx]), delimiter=delim)
    columns = next(reader, [])
    columns = [_norm(c) for c in columns]
    if not columns:
        return [], []

    # Datos hasta línea vacía o hasta encontrar otro marcador común
    stop_markers = ("RESULTS", "CONTROL STATISTICS", "ASSET TAGS", "SUMMARY")
    data_lines: List[str] = []
    for k in range(hdr_idx + 1, n):
        ln = lines[k]
        if not ln.strip():
            break
        if _norm(ln).upper() in stop_markers:
            break
        data_lines.append(ln)

    rows: List[Dict[str, str]] = []
    rdr = csv.reader(io.StringIO("\n".join(data_lines)), delimiter=delim)
    for row in rdr:
        # tolerante: si falta/n sobra(n) columnas, recorta o rellena
        if len(row) < len(columns):
            row = list(row) + [""] * (len(columns) - len(row))
        elif len(row) > len(columns):
            row = row[:len(columns)]
        obj = {columns[i]: _norm(row[i]) for i in range(len(columns))}
        rows.append(obj)

    return rows, columns

def _extract_os(head_text: str) -> Optional[str]:
    """
    Ejemplos:
      - "CIS Benchmark for Microsoft Windows server 2003 v3.1.0 ..."
      - "CIS IBM AIX 7.3 Benchmark v1.1.0 ..."
    Salida:
      - "Microsoft Windows server 2003"
      - "IBM AIX 7.3"
    """
    patterns = [
        r"CIS\s+Benchmark\s+for\s+(.+?)\s+v\d",
        r"CIS\s+(.+?)\s+Benchmark\s+v\d",
        r"CIS\s+Benchmark\s+for\s+(.+?)\s+version\s+\d",
        r"CIS\s+(.+?)\s+Benchmark\s+version\s+\d",
    ]
    for pat in patterns:
        m = re.search(pat, head_text, flags=re.IGNORECASE)
        if m:
            os_name = m.group(1).strip()
            return re.sub(r"\s+", " ", os_name)
    return None

def parse_csv_file(
    path: Path,
    empresas: List[str],
    nombre_defecto: str
) -> Tuple[bool, str, List[dict], List[str], List[dict], List[str], Optional[str]]:
    """
    Devuelve:
      (es_ajustada, cliente_detectado,
       t1_rows, t1_cols,
       t2_rows, t2_cols,
       os_name)
    """
    # --- Heurística inicial: ajustada/cliente/os en primeras líneas ---
    es_ajustada = False
    cliente = nombre_defecto
    os_name: Optional[str] = None

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        head_lines = []
        for _ in range(8):
            ln = f.readline()
            if not ln:
                break
            head_lines.append(ln)
        head_text = " ".join(head_lines)
        es_ajustada = any(tok in head_text.upper() for tok in AJUSTADA_TOKENS)
        low = head_text.lower()
        for e in empresas:
            if e.lower() in low:
                cliente = e
                break
        os_name = _extract_os(head_text)

    # Reabrimos para parsear todo desde cero (no dependemos del primer read)
    t1_rows: List[dict] = []
    t2_rows: List[dict] = []
    t1_cols: List[str] = []
    t2_cols: List[str] = []

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        pending_line: Optional[str] = None

        def next_line() -> str:
            nonlocal pending_line
            if pending_line is not None:
                ln = pending_line
                pending_line = None
                return ln
            return f.readline()

        while True:
            # Avanza hasta encontrar un marcador de sección
            marker = ""
            while True:
                ln = next_line()
                if not ln:
                    marker = ""
                    break
                s = _norm(ln)
                if not s:
                    continue
                if _is_any_marker(s):
                    marker = s
                    break
            if not marker:
                break  # EOF

            # Header = siguiente línea no vacía
            header_line = ""
            while True:
                ln = next_line()
                if not ln:
                    break
                if ln.strip():
                    header_line = ln
                    break
            if not header_line:
                # marcador sin header; continúa buscando siguiente sección
                continue

            delim = _detect_delimiter(header_line)
            # Columnas (limpiamos comillas)
            cols = next(csv.reader([header_line], delimiter=delim), [])
            cols = [_norm(c) for c in cols]
            # Aseguramos 'Cliente'
            if "Cliente" not in cols:
                cols.append("Cliente")

            # Iterador de la sección: entrega líneas hasta el próximo marcador
            class _SectionIter:
                def __init__(self):
                    self.stopped_line: Optional[str] = None
                def __iter__(self):
                    return self
                def __next__(self):
                    nonlocal pending_line
                    ln = f.readline()
                    if ln == "":
                        raise StopIteration
                    s = _norm(ln)
                    if _is_any_marker(s):
                        # guardamos el marcador para el próximo ciclo y cerramos esta sección
                        pending_line = ln
                        raise StopIteration
                    return ln

            it = _SectionIter()
            rdr = csv.reader(it, delimiter=delim)

            # Procesar filas de la sección
            is_t1 = _is_t1_marker(marker)
            is_t2 = _is_t2_marker(marker)
            # Host Statistics: lo ignoramos
            for row in rdr:
                # normaliza tamaño vs columnas sin contar 'Cliente'
                need = len(cols) - 1
                row = list(row)
                if len(row) < need:
                    row += [""] * (need - len(row))
                elif len(row) > need:
                    row = row[:need]

                obj = {cols[i]: _norm(row[i]) for i in range(need)}
                obj["Cliente"] = cliente
                if os_name:
                    obj["os"] = os_name

                if is_t1:
                    if not t1_cols:
                        t1_cols = cols[:]  # conserva orden del primer header T1
                    t1_rows.append(obj)
                elif is_t2:
                    if not t2_cols:
                        t2_cols = cols[:]
                    t2_rows.append(obj)
                else:
                    # Host Statistics: ignorado
                    pass

            # Siguiente iteración usará 'pending_line' como nuevo marcador (si quedó algo)

    return es_ajustada, cliente, t1_rows, t1_cols, t2_rows, t2_cols, os_name