from __future__ import annotations
from pathlib import Path
from datetime import datetime
import calendar
from typing import List, Dict, Optional
from openpyxl import Workbook

MESES_ES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}

def _nombre_base(cliente: str, es_control: bool, es_ajustada: bool) -> tuple[str, str]:
    hoy = datetime.today()
    anio, mes = hoy.year, hoy.month
    dia = calendar.monthrange(anio, mes)[1]
    base = f"{cliente}-hardening{'-control-statics' if es_control else ''}-{anio}-{MESES_ES[mes]}-{dia:02d}"
    if es_ajustada:
        base += "-ajustado"
    # scan_name y periodo (columnas adicionales)
    scan_name = base
    periodo = f"{mes}/{dia}/{anio}"
    return base, f"{scan_name}|{periodo}"  # empaquetamos ambos

class _XlsxWriter:
    def __init__(self, path: Path, header_cols: List[str], scan_name: str, periodo: str):
        self.path = path
        self.header_cols = header_cols[:]  # columnas "originales" + Cliente
        self.scan_name = scan_name
        self.periodo = periodo
        self.count = 0

        path.parent.mkdir(parents=True, exist_ok=True)
        self.wb = Workbook(write_only=True)
        self.ws = self.wb.create_sheet(title="data")
        # header: columnas + extras
        header = self.header_cols + ["scan_name", "periodo"]
        self.ws.append(header)

    def append(self, row: Dict[str, str]):
        data = [row.get(c, "") for c in self.header_cols]
        data.append(self.scan_name)
        data.append(self.periodo)
        self.ws.append(data)
        self.count += 1

    def close(self):
        self.wb.save(str(self.path))
        self.wb.close()

class ExcelAggregator:
    """
    Mantiene hasta 4 libros abiertos y escribe filas a medida que llegan.
    t1 = Control Statistics, t2 = RESULTS
    """
    def __init__(self, cliente: str, out_dir: Path):
        self.cliente = cliente
        self.out_dir = out_dir
        # columnas maestras (fijadas con el primer CSV que traiga cada tabla)
        self.t1_cols: Optional[List[str]] = None
        self.t2_cols: Optional[List[str]] = None
        # writers perezosos
        self.w_t1_norm: Optional[_XlsxWriter] = None
        self.w_t1_aj:   Optional[_XlsxWriter] = None
        self.w_t2_norm: Optional[_XlsxWriter] = None
        self.w_t2_aj:   Optional[_XlsxWriter] = None
        # conteos
        self.counts = {"t1_normal":0, "t1_ajustada":0, "t2_normal":0, "t2_ajustada":0}
        # previas ligeras
        self.preview = {"t1_normal":[], "t1_ajustada":[], "t2_normal":[], "t2_ajustada":[]}
        self.preview_limit = 50
        # archivos guardados
        self.saved_files: List[str] = []

    def _ensure_writer(self, table: str, ajustada: bool, header_cols: List[str]) -> _XlsxWriter:
        # fijar columnas maestras la primera vez
        if table == "t1" and self.t1_cols is None:
            self.t1_cols = header_cols[:]
        if table == "t2" and self.t2_cols is None:
            self.t2_cols = header_cols[:]

        is_control = (table == "t1")
        base, sn_per = _nombre_base(self.cliente, es_control=is_control, es_ajustada=ajustada)
        scan_name, periodo = sn_per.split("|", 1)
        path = self.out_dir / f"{base}.xlsx"

        if is_control:
            if ajustada and self.w_t1_aj is None:
                self.w_t1_aj = _XlsxWriter(path, self.t1_cols, scan_name, periodo)
            if not ajustada and self.w_t1_norm is None:
                self.w_t1_norm = _XlsxWriter(path, self.t1_cols, scan_name, periodo)
            return self.w_t1_aj if ajustada else self.w_t1_norm
        else:
            if ajustada and self.w_t2_aj is None:
                self.w_t2_aj = _XlsxWriter(path, self.t2_cols, scan_name, periodo)
            if not ajustada and self.w_t2_norm is None:
                self.w_t2_norm = _XlsxWriter(path, self.t2_cols, scan_name, periodo)
            return self.w_t2_aj if ajustada else self.w_t2_norm

    def add_row(self, table: str, ajustada: bool, row: Dict[str,str], header_cols: List[str]):
        w = self._ensure_writer(table, ajustada, header_cols)
        w.append(row)
        key = f"{'t1' if table=='t1' else 't2'}_{'ajustada' if ajustada else 'normal'}"
        self.counts[key] += 1
        if len(self.preview[key]) < self.preview_limit:
            self.preview[key].append(row)

    def close(self):
        for w in [self.w_t1_norm, self.w_t1_aj, self.w_t2_norm, self.w_t2_aj]:
            if w:
                w.close()
                self.saved_files.append(Path(w.path).name)
        return self.saved_files
