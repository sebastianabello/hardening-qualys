import csv
import io
from pathlib import Path
from typing import List, Tuple, Dict

# Palabras para detectar "ajustada" (cabecera o primeras líneas)
AJUSTADA_TOKENS = ("AJUSTA", "AJUSTADA", "AJU")

def _norm(s: str) -> str:
    return s.strip().strip('"').strip("'")

def _is_marker(line: str, target: str) -> bool:
    return _norm(line).upper() == target.upper()

def _detect_delimiter(sample_line: str) -> str:
    # simple: cuenta comas vs punto y coma
    c, sc = sample_line.count(","), sample_line.count(";")
    if sc > c:
        return ";"
    return ","

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

def parse_csv_file(path: Path, empresas: List[str], nombre_defecto: str) -> Tuple[bool, str, List[Dict], List[str], List[Dict], List[str]]:
    """
    Devuelve:
      es_ajustada, cliente_detectado, t1_rows, t1_cols, t2_rows, t2_cols
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    es_ajustada = detect_ajustada(lines)
    cliente = detect_cliente(lines, empresas, nombre_defecto)

    t1_rows, t1_cols = _extract_table(lines, "Control Statistics (Percentage of Hosts Passed per Control)")
    t2_rows, t2_cols = _extract_table(lines, "RESULTS")

    # Añade Cliente a cada fila (se respeta estructura original)
    for r in t1_rows:
        r["Cliente"] = cliente
    for r in t2_rows:
        r["Cliente"] = cliente

    return es_ajustada, cliente, t1_rows, t1_cols + (["Cliente"] if "Cliente" not in t1_cols else []), t2_rows, t2_cols + (["Cliente"] if "Cliente" not in t2_cols else [])
