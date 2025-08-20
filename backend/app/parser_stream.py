from __future__ import annotations
from pathlib import Path
from typing import Iterator, Tuple, List, Dict
import csv, io, re

AJUSTADA_TOKENS = ("AJUSTA", "AJUSTADA", "AJU")

def _norm(s: str) -> str:
    return s.strip().strip('"').strip("'")

def _is_marker(line: str, target: str) -> bool:
    return _norm(line).upper() == target.upper()

def _detect_delimiter(sample: str) -> str:
    return ";" if sample.count(";") > sample.count(",") else ","

def _extract_os(head_text: str) -> str | None:
    """
    Extrae el nombre de SO desde textos tipo:
      - "CIS Benchmark for Microsoft Windows server 2003 v3.1.0 ..."
      - "CIS IBM AIX 7.3 Benchmark v1.1.0 ..."
    Devuelve:
      - "Microsoft Windows server 2003"
      - "IBM AIX 7.3"
    """
    patterns = [
        r"CIS\s+Benchmark\s+for\s+(.+?)\s+v\d",          # ... Benchmark for <OS> vX
        r"CIS\s+(.+?)\s+Benchmark\s+v\d",                # CIS <OS> Benchmark vX
        r"CIS\s+Benchmark\s+for\s+(.+?)\s+version\s+\d", # ... Benchmark for <OS> version X
        r"CIS\s+(.+?)\s+Benchmark\s+version\s+\d",       # CIS <OS> Benchmark version X
    ]
    for pat in patterns:
        m = re.search(pat, head_text, flags=re.IGNORECASE)
        if m:
            os_name = m.group(1).strip()
            os_name = re.sub(r"\s+", " ", os_name)
            return os_name
    return None

def _detect_head(path: Path, empresas: List[str], nombre_defecto: str) -> Tuple[bool, str, str | None]:
    es_ajustada = False
    cliente = nombre_defecto
    os_name: str | None = None
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        head = []
        for _ in range(5):
            ln = f.readline()
            if not ln: break
            head.append(ln)
        head_join = " ".join(head)

        es_ajustada = any(tok in head_join.upper() for tok in AJUSTADA_TOKENS)
        low = head_join.lower()
        for e in empresas:
            if e.lower() in low:
                cliente = e
                break

        os_name = _extract_os(head_join)
    return es_ajustada, cliente, os_name

def stream_tables(path: Path, empresas: List[str], nombre_defecto: str) -> Iterator[Tuple[str, bool, Dict[str,str], List[str], str | None]]:
    """
    Emite tuplas (table, es_ajustada, row_dict, header_cols, os_name)
      table in {"t1","t2"}
    """
    es_ajustada, cliente, os_name = _detect_head(path, empresas, nombre_defecto)

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        while True:
            line = f.readline()
            if not line: break

            is_t1 = _is_marker(line, "Control Statistics")
            is_t2 = _is_marker(line, "RESULTS")
            if not (is_t1 or is_t2):
                continue

            # Header = próxima línea no vacía
            hdr = ""
            while True:
                l2 = f.readline()
                if not l2: break
                if l2.strip():
                    hdr = l2
                    break
            if not hdr:
                continue

            delim = _detect_delimiter(hdr)
            columns = next(csv.reader([hdr], delimiter=delim), [])
            columns = [_norm(c) for c in columns]
            if "Cliente" not in columns:
                columns.append("Cliente")  # añadimos Cliente en dataset

            def data_iter():
                while True:
                    p = f.tell()
                    ln = f.readline()
                    if not ln or not ln.strip():
                        break
                    if _is_marker(ln, "RESULTS") or _is_marker(ln, "Control Statistics") or _norm(ln).upper() in ("ASSET TAGS","SUMMARY"):
                        f.seek(p)
                        break
                    yield ln

            rdr = csv.reader(data_iter(), delimiter=delim)
            for row in rdr:
                # tamaño vs columnas (tolerante)
                need = len(columns) - 1  # sin "Cliente"
                if len(row) < need: row = list(row) + [""] * (need - len(row))
                elif len(row) > need: row = row[:need]

                obj = {columns[i]: _norm(row[i]) for i in range(need)}
                obj["Cliente"] = cliente
                yield ("t1" if is_t1 else "t2", es_ajustada, obj, columns, os_name)
