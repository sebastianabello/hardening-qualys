from pathlib import Path
from datetime import datetime
import calendar
from typing import List, Dict, Tuple
import csv  # 👈 ahora escribimos CSV

MESES_ES = {
    1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
    7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"
}

def _nombre_base(cliente_padre: str, es_control: bool, es_ajustada: bool) -> Tuple[str, int, int, int]:
    hoy = datetime.today()
    anio, mes = hoy.year, hoy.month
    dia = calendar.monthrange(anio, mes)[1]
    base = f"{cliente_padre}-hardening{'-control-statics' if es_control else ''}-{anio}-{MESES_ES[mes]}-{dia:02d}"
    if es_ajustada:
        base += "-ajustado"
    return base, anio, mes, dia

def _write_csv(rows, columns, out_path: Path, scan_name: str, periodo: str):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # header (+ columnas extra)
    header = list(columns)
    if "os" not in header:
        header.append("os")
    if "scan_name" not in header:
        header.append("scan_name")
    if "periodo" not in header:
        header.append("periodo")

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        for r in rows:
            row = [r.get(c, "") for c in columns]
            row.append(r.get("os",""))
            row.append(scan_name)
            row.append(periodo)
            w.writerow(row)

def guardar_cuatro_excels(  # 👈 conservamos el nombre por compatibilidad
    t1_normal: List[Dict[str, str]], t1_cols: List[str],
    t1_ajustada: List[Dict[str, str]],
    t2_normal: List[Dict[str, str]], t2_cols: List[str],
    t2_ajustada: List[Dict[str, str]],
    cliente_padre: str, carpeta: Path
) -> List[str]:
    """
    Genera hasta 4 archivos CSV (solo si hay filas):
      - control normal
      - control ajustada
      - results normal
      - results ajustada
    Devuelve nombres (relative to carpeta) en el orden que existan.
    """
    nombres: List[str] = []

    # T1 normal
    if t1_normal:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=True, es_ajustada=False)
        _write_csv(t1_normal, t1_cols, carpeta / f"{base}.csv", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.csv")

    # T1 ajustada
    if t1_ajustada:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=True, es_ajustada=True)
        _write_csv(t1_ajustada, t1_cols, carpeta / f"{base}.csv", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.csv")

    # T2 normal
    if t2_normal:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=False, es_ajustada=False)
        _write_csv(t2_normal, t2_cols, carpeta / f"{base}.csv", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.csv")

    # T2 ajustada
    if t2_ajustada:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=False, es_ajustada=True)
        _write_csv(t2_ajustada, t2_cols, carpeta / f"{base}.csv", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.csv")

    return nombres
