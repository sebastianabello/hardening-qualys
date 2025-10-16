from __future__ import annotations
from pathlib import Path
from datetime import datetime
import calendar, csv, gzip, subprocess, shutil
from typing import List, Dict, Optional
from .settings import settings
import logging

logger = logging.getLogger(__name__)

MESES_ES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}

def _nombre_base(cliente: str, es_control: bool, es_ajustada: bool):
    hoy = datetime.today()
    anio, mes = hoy.year, hoy.month
    dia = calendar.monthrange(anio, mes)[1]
    base = f"{cliente}-hardening{'-control-statics' if es_control else ''}-{anio}-{MESES_ES[mes]}-{dia:02d}"
    if es_ajustada:
        base += "-ajustado"
    scan_name = base
    periodo = f"{mes}/{dia}/{anio}"
    return base, scan_name, periodo

class _CsvWriter:
    def __init__(self, path: Path, header_cols: List[str], scan_name: str, periodo: str):
        self.path = path
        self.cols = header_cols[:]
        self.scan_name = scan_name
        self.periodo = periodo
        self.count = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Compresión con pigz (paralelo) si está disponible
        if settings.CSV_GZIP:
            # Intentar usar pigz para compresión paralela
            if settings.ENABLE_PARALLEL_COMPRESSION and shutil.which("pigz"):
                logger.info(f"🚀 Usando pigz (compresión paralela) para {path.name}")
                # Crear proceso pigz
                self.pigz_proc = subprocess.Popen(
                    ['pigz', '-c', '-1', '-p', str(settings.WORKER_PROCESSES)],  # -1 = rápido, -p = threads
                    stdin=subprocess.PIPE,
                    stdout=open(path, 'wb'),
                    stderr=subprocess.PIPE
                )
                self.fh = self.pigz_proc.stdin
                self.using_pigz = True
            else:
                # Fallback a gzip estándar
                logger.info(f"ℹ️ Usando gzip estándar para {path.name}")
                self.fh = gzip.open(path, "wt", encoding="utf-8", newline="", compresslevel=1)
                self.using_pigz = False
        else:
            # Sin compresión - buffer mucho más grande para escritura rápida
            self.fh = path.open("w", encoding="utf-8", newline="", buffering=settings.WRITE_BUFFER_SIZE)
            self.using_pigz = False
        
        self.w = csv.writer(self.fh, quoting=csv.QUOTE_MINIMAL)
        header = self.cols + ["scan_name","periodo","os"]
        self.w.writerow(header)
        self._row_buffer = []
        self._buffer_size = 1000  # Escribir cada 1000 filas

    def append(self, row: Dict[str,str], os_value: Optional[str]):
        out = [row.get(c, "") for c in self.cols]
        out.append(self.scan_name)
        out.append(self.periodo)
        out.append(os_value or "")
        self._row_buffer.append(out)
        self.count += 1
        
        # Flush buffer cada N filas para mejor rendimiento
        if len(self._row_buffer) >= self._buffer_size:
            self._flush_buffer()
    
    def _flush_buffer(self):
        if self._row_buffer:
            self.w.writerows(self._row_buffer)
            self._row_buffer.clear()

    def close(self):
        try:
            self._flush_buffer()  # Flush cualquier fila pendiente
            self.fh.flush()
        finally:
            if hasattr(self, 'using_pigz') and self.using_pigz:
                # Cerrar pigz correctamente
                self.fh.close()
                self.pigz_proc.wait()
                if self.pigz_proc.returncode != 0:
                    stderr = self.pigz_proc.stderr.read()
                    logger.warning(f"⚠️ pigz warning: {stderr}")
            else:
                self.fh.close()

class CsvAggregator:
    """
    Abre hasta 4 CSV y escribe en streaming con partición por filas:
      t1_normal, t1_ajustada, t2_normal, t2_ajustada
    """
    def __init__(self, cliente: str, out_dir: Path):
        self.cliente = cliente
        self.out_dir = out_dir
        self.t1_cols: Optional[List[str]] = None
        self.t2_cols: Optional[List[str]] = None

        # writers actuales
        self.w_t1_n: Optional[_CsvWriter] = None
        self.w_t1_a: Optional[_CsvWriter] = None
        self.w_t2_n: Optional[_CsvWriter] = None
        self.w_t2_a: Optional[_CsvWriter] = None

        # contador de partes
        self.p_t1_n = 1
        self.p_t1_a = 1
        self.p_t2_n = 1
        self.p_t2_a = 1

        self.counts = {"t1_normal":0,"t1_ajustada":0,"t2_normal":0,"t2_ajustada":0}
        self.preview = {"t1_normal":[], "t1_ajustada":[], "t2_normal":[], "t2_ajustada":[]}
        self.preview_limit = 50
        self.saved_files: List[str] = []

    def _build_path(self, base: str, part: int) -> Path:
        suf = ".csv.gz" if settings.CSV_GZIP else ".csv"
        # agrega sufijo -part-02 a partir de la parte 2
        name = f"{base}{'' if part==1 else f'-part-{part:02d}'}{suf}"
        return self.out_dir / name

    def _ensure_writer(self, table: str, ajustada: bool, header_cols: List[str]) -> _CsvWriter:
        is_control = (table == "t1")
        if is_control and self.t1_cols is None:
            self.t1_cols = header_cols[:]
        if not is_control and self.t2_cols is None:
            self.t2_cols = header_cols[:]

        base, scan_name, periodo = _nombre_base(self.cliente, es_control=is_control, es_ajustada=ajustada)

        if is_control:
            if ajustada:
                if self.w_t1_a is None:
                    self.w_t1_a = _CsvWriter(self._build_path(base, self.p_t1_a), self.t1_cols, scan_name, periodo)
                return self.w_t1_a
            else:
                if self.w_t1_n is None:
                    self.w_t1_n = _CsvWriter(self._build_path(base, self.p_t1_n), self.t1_cols, scan_name, periodo)
                return self.w_t1_n
        else:
            if ajustada:
                if self.w_t2_a is None:
                    self.w_t2_a = _CsvWriter(self._build_path(base, self.p_t2_a), self.t2_cols, scan_name, periodo)
                return self.w_t2_a
            else:
                if self.w_t2_n is None:
                    self.w_t2_n = _CsvWriter(self._build_path(base, self.p_t2_n), self.t2_cols, scan_name, periodo)
                return self.w_t2_n

    def _rotate_if_needed(self, writer_attr: str, part_attr: str, base: str, cols: List[str]):
        """Cierra el writer actual y abre el siguiente si se alcanzó el límite."""
        writer: _CsvWriter = getattr(self, writer_attr)
        if writer and writer.count >= settings.CSV_PART_MAX_ROWS:
            # guarda nombre del archivo recién cerrado
            writer.close()
            self.saved_files.append(Path(writer.path).name)
            # incrementa parte y reabre
            part = getattr(self, part_attr) + 1
            setattr(self, part_attr, part)
            # re-crear writer con las mismas columnas
            base_scan, scan_name, periodo = _nombre_base(self.cliente,
                                                         es_control="-control-statics" in base,
                                                         es_ajustada="-ajustado" in base)
            # Nota: base ya trae control/ajustada; usamos esas columas:
            new_path = self._build_path(base, part)
            new_writer = _CsvWriter(new_path, cols, scan_name, periodo)
            setattr(self, writer_attr, new_writer)

    def add_row(self, table: str, ajustada: bool, row: Dict[str,str], header_cols: List[str], os_value: Optional[str]):
        w = self._ensure_writer(table, ajustada, header_cols)
        w.append(row, os_value)

        key = f"{'t1' if table=='t1' else 't2'}_{'ajustada' if ajustada else 'normal'}"
        self.counts[key] += 1
        if len(self.preview[key]) < self.preview_limit:
            r2 = dict(row)
            r2["os"] = os_value or ""
            self.preview[key].append(r2)

        # rotación si se alcanzó el límite
        base, _, _ = _nombre_base(self.cliente, es_control=(table=="t1"), es_ajustada=ajustada)
        if table == "t1" and not ajustada:
            self._rotate_if_needed("w_t1_n", "p_t1_n", base, self.t1_cols)
        elif table == "t1" and ajustada:
            self._rotate_if_needed("w_t1_a", "p_t1_a", base, self.t1_cols)
        elif table == "t2" and not ajustada:
            self._rotate_if_needed("w_t2_n", "p_t2_n", base, self.t2_cols)
        else:
            self._rotate_if_needed("w_t2_a", "p_t2_a", base, self.t2_cols)

    def close(self):
        # Cierra abiertos y registra nombres
        for attr in ["w_t1_n","w_t1_a","w_t2_n","w_t2_a"]:
            w: Optional[_CsvWriter] = getattr(self, attr)
            if w:
                w.close()
                self.saved_files.append(Path(w.path).name)
                setattr(self, attr, None)
        return self.saved_files
