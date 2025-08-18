from pathlib import Path
from datetime import datetime
import calendar
from typing import List, Dict, Tuple
from openpyxl import Workbook


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

def _write_xlsx(rows, columns, out_path, scan_name, periodo):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook(write_only=True)

    # En write-only NO hay hoja por defecto: solo creamos una y NO la removemos
    ws = wb.create_sheet(title="data")

    # Header (+ columnas extra)
    header = list(columns)
    if "scan_name" not in header:
        header.append("scan_name")
    if "periodo" not in header:
        header.append("periodo")
    ws.append(header)

    # Filas
    for r in rows:
        row = [r.get(c, "") for c in columns]
        row.append(scan_name)
        row.append(periodo)
        ws.append(row)

    # Guardar y cerrar
    wb.save(str(out_path))
    wb.close()


def guardar_cuatro_excels(
    t1_normal: List[Dict[str, str]], t1_cols: List[str],
    t1_ajustada: List[Dict[str, str]],
    t2_normal: List[Dict[str, str]], t2_cols: List[str],
    t2_ajustada: List[Dict[str, str]],
    cliente_padre: str, carpeta: Path
) -> List[str]:
    """
    Genera hasta 4 archivos (solo si hay filas):
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
        _write_xlsx(t1_normal, t1_cols, carpeta / f"{base}.xlsx", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.xlsx")
    # T1 ajustada
    if t1_ajustada:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=True, es_ajustada=True)
        _write_xlsx(t1_ajustada, t1_cols, carpeta / f"{base}.xlsx", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.xlsx")
    # T2 normal
    if t2_normal:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=False, es_ajustada=False)
        _write_xlsx(t2_normal, t2_cols, carpeta / f"{base}.xlsx", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.xlsx")
    # T2 ajustada
    if t2_ajustada:
        base, anio, mes, dia = _nombre_base(cliente_padre, es_control=False, es_ajustada=True)
        _write_xlsx(t2_ajustada, t2_cols, carpeta / f"{base}.xlsx", base, f"{mes}/{dia}/{anio}")
        nombres.append(f"{base}.xlsx")

    return nombres
