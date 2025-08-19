from __future__ import annotations
from pathlib import Path
from typing import Iterator, Tuple, List, Dict
import csv, io

AJUSTADA_TOKENS = ("AJUSTA", "AJUSTADA", "AJU")

def _norm(s: str) -> str:
    return s.strip().strip('"').strip("'")

def _is_marker(line: str, target: str) -> bool:
    return _norm(line).upper() == target.upper()

def _detect_delimiter(sample: str) -> str:
    return ";" if sample.count(";") > sample.count(",") else ","

def _detect_head(path: Path, empresas: List[str], nombre_defecto: str) -> Tuple[bool, str]:
    es_ajustada = False
    cliente = nombre_defecto
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
    return es_ajustada, cliente

def stream_tables(path: Path, empresas: List[str], nombre_defecto: str) -> Iterator[Tuple[str, bool, Dict[str,str], List[str]]]:
    """
    Emite tuplas (table, es_ajustada, row_dict, header_cols)
      table in {"t1","t2"}
    """
    es_ajustada, cliente = _detect_head(path, empresas, nombre_defecto)

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        n = 0
        while True:
            pos = f.tell()
            line = f.readline()
            if not line: break
            n += 1

            # Buscar T1 o T2
            is_t1 = _is_marker(line, "Control Statistics")
            is_t2 = _is_marker(line, "RESULTS")
            if not (is_t1 or is_t2):
                continue

            # Header: próxima línea no vacía
            hdr = ""
            while True:
                pos2 = f.tell()
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
            # Asegura columna Cliente
            if "Cliente" not in columns:
                columns.append("Cliente")

            # Iterador de datos hasta línea vacía o próximo marcador
            def data_iter():
                nonlocal f
                while True:
                    p = f.tell()
                    ln = f.readline()
                    if not ln:
                        break
                    if not ln.strip():
                        break
                    if _is_marker(ln, "RESULTS") or _is_marker(ln, "Control Statistics") or _norm(ln).upper() in ("ASSET TAGS","SUMMARY"):
                        # retrocede para que el for externo procese el marcador
                        f.seek(p)
                        break
                    yield ln

            rdr = csv.reader(data_iter(), delimiter=delim)
            for row in rdr:
                # normaliza tamaño vs columnas (tolerante)
                if len(row) < len(columns)-1:  # -1 porque añadimos "Cliente" quizá
                    row = list(row) + [""] * (len(columns)-1 - len(row))
                elif len(row) > len(columns)-1:
                    row = row[:len(columns)-1]

                obj = {columns[i]: _norm(row[i]) for i in range(len(columns)-1)}
                obj["Cliente"] = cliente

                yield ("t1" if is_t1 else "t2", es_ajustada, obj, columns)
