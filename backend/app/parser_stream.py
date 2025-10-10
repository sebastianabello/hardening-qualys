from __future__ import annotations
from pathlib import Path
from typing import Iterator, Tuple, List, Dict, Optional
import csv, re, sys

AJUSTADA_TOKENS = ("AJUSTA","AJUSTADA","AJU")

try:
    csv.field_size_limit(10 * 1024 * 1024)   # 10 MB por campo (ajústalo si hace falta)
except Exception:
    # Fallback seguro para entornos 32-bit
    csv.field_size_limit(min(sys.maxsize, 2_147_483_647))

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
    return _is_t1_marker(s) or _is_t2_marker(s) or _is_host_marker(s) or s.upper() in ("ASSET TAGS","SUMMARY")

def _detect_delimiter(header_line: str) -> str:
    return ";" if header_line.count(";") > header_line.count(",") else ","

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
            return re.sub(r"\s+"," ",m.group(1).strip())
    return None

def _detect_head(path: Path, empresas: List[str], nombre_defecto: str) -> tuple[bool,str,Optional[str]]:
    es_ajustada = False
    cliente = nombre_defecto
    os_name: Optional[str] = None
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        head = []
        for _ in range(10):
            ln = f.readline()
            if not ln: break
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

def stream_tables(path: Path, empresas: List[str], nombre_defecto: str) -> Iterator[Tuple[str,bool,Dict[str,str],List[str],Optional[str]]]:
    """
    Yields: (table ['t1'|'t2'], es_ajustada, row_dict, header_cols, os_name)
    - Ignora 'Host Statistics'
    - Soporta campos multilínea (csv.reader con newline="")
    - Sección termina SOLO cuando aparece otro marcador
    """
    es_ajustada, cliente, os_name = _detect_head(path, empresas, nombre_defecto)

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        pending: Optional[str] = None

        def next_line() -> str:
            nonlocal pending
            if pending is not None:
                ln = pending; pending = None; return ln
            return f.readline()

        while True:
            # Busca un marcador
            marker = ""
            while True:
                ln = next_line()
                if not ln: break
                s = _norm(ln)
                if not s: continue
                if _is_any_marker(s):
                    marker = s
                    break
            if not marker:
                break  # EOF

            # Header de la sección
            header_line = ""
            while True:
                ln = next_line()
                if not ln: break
                if ln.strip():
                    header_line = ln
                    break
            if not header_line:
                continue

            delim = _detect_delimiter(header_line)
            cols = next(csv.reader([header_line], delimiter=delim), [])
            cols = [_norm(c) for c in cols]
            if "Cliente" not in cols:
                cols.append("Cliente")

            class SectionIter:
                def __iter__(self): return self
                def __next__(self):
                    nonlocal pending
                    ln = f.readline()
                    if ln == "": raise StopIteration
                    s = _norm(ln)
                    if _is_any_marker(s):
                        pending = ln
                        raise StopIteration
                    return ln

            is_t1 = _is_t1_marker(marker)
            is_t2 = _is_t2_marker(marker)
            if not (is_t1 or is_t2):
                # Host Statistics u otros → saltar sección completa
                for _ in csv.reader(SectionIter(), delimiter=delim):
                    pass
                continue

            rdr = csv.reader(SectionIter(), delimiter=delim)
            need = len(cols) - 1  # sin 'Cliente'
            for row in rdr:
                row = list(row)
                if len(row) < need: row += [""] * (need - len(row))
                elif len(row) > need: row = row[:need]
                obj = {cols[i]: _norm(row[i]) for i in range(need)}
                obj["Cliente"] = cliente
                yield ("t1" if is_t1 else "t2", es_ajustada, obj, cols, os_name)
