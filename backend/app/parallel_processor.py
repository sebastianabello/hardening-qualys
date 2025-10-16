"""
Procesamiento paralelo optimizado para archivos CSV grandes.
Utiliza PyArrow para parsing ultra-rápido cuando está disponible.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from multiprocessing import Pool, cpu_count
import logging

logger = logging.getLogger(__name__)

# Intentar importar parser optimizado
try:
    from .parser_arrow import stream_tables_arrow, PYARROW_AVAILABLE
    if PYARROW_AVAILABLE:
        logger.info("✅ Usando parser PyArrow ultra-rápido")
        stream_tables_func = stream_tables_arrow
    else:
        from .parser_stream import stream_tables
        stream_tables_func = stream_tables
        logger.info("ℹ️ PyArrow no disponible, usando parser estándar")
except ImportError:
    from .parser_stream import stream_tables
    stream_tables_func = stream_tables
    logger.info("ℹ️ Usando parser estándar")

from .csv_stream import CsvAggregator
from .settings import settings


def _process_single_csv(args: Tuple[Path, List[str], str, Path]) -> Tuple[str, Dict, List[str]]:
    """
    Procesa un solo CSV y retorna los datos acumulados.
    Esta función se ejecuta en un proceso separado.
    
    Returns:
        (filename, {table: rows_list}, warnings)
    """
    csv_path, empresas_list, nombre_defecto, temp_dir = args
    
    filename = csv_path.name
    file_size_mb = csv_path.stat().st_size / 1024 / 1024
    
    logger.info(f"🔄 Worker procesando: {filename} ({file_size_mb:.1f} MB)")
    
    # Acumuladores temporales para este archivo
    data = {
        't1_normal': [],
        't1_ajustada': [],
        't2_normal': [],
        't2_ajustada': []
    }
    
    cols_by_table = {
        't1': None,
        't2': None
    }
    
    warnings = []
    saw_t1 = saw_t2 = False
    rows_processed = 0
    
    try:
        for table, es_aj, row, cols, os_name in stream_tables(csv_path, empresas_list, nombre_defecto):
            if table == "t1": 
                saw_t1 = True
                if cols_by_table['t1'] is None:
                    cols_by_table['t1'] = cols
            if table == "t2": 
                saw_t2 = True
                if cols_by_table['t2'] is None:
                    cols_by_table['t2'] = cols
            
            # Agregar OS al row
            row['os'] = os_name or ""
            
            key = f"{'t1' if table=='t1' else 't2'}_{'ajustada' if es_aj else 'normal'}"
            data[key].append(row)
            rows_processed += 1
            
            # Log cada 50k filas
            if rows_processed % 50000 == 0:
                logger.info(f"   {filename}: {rows_processed:,} filas procesadas")
        
        logger.info(f"✅ {filename}: {rows_processed:,} filas totales")
        
        if not saw_t1:
            warnings.append(f"{filename}: 'Control Statistics' no encontrada o vacía")
        if not saw_t2:
            warnings.append(f"{filename}: 'RESULTS' no encontrada o vacía")
        
        return (filename, data, warnings, cols_by_table)
        
    except Exception as ex:
        logger.error(f"❌ Error procesando {filename}: {ex}")
        warnings.append(f"{filename}: error de parseo: {ex}")
        return (filename, data, warnings, cols_by_table)


class ParallelCsvProcessor:
    """
    Procesador paralelo de CSVs usando multiprocessing.
    Ideal para archivos muy grandes (>100MB).
    """
    
    def __init__(self, cliente: str, out_dir: Path, num_workers: Optional[int] = None):
        self.cliente = cliente
        self.out_dir = out_dir
        self.num_workers = num_workers or min(settings.WORKER_PROCESSES, cpu_count())
        self.aggregator = CsvAggregator(cliente=cliente, out_dir=out_dir)
        
    def process_csvs_parallel(
        self, 
        csv_paths: List[Path], 
        empresas_list: List[str], 
        nombre_defecto: str,
        progress_callback = None
    ) -> Tuple[List[str], List[str], Dict]:
        """
        Procesa múltiples CSVs en paralelo.
        
        Args:
            csv_paths: Lista de rutas a archivos CSV
            empresas_list: Lista de empresas para detección
            nombre_defecto: Nombre por defecto del cliente
            progress_callback: Función callback(filename, rows_processed, total_files)
            
        Returns:
            (nombres_archivos_generados, warnings, counts)
        """
        total_csvs = len(csv_paths)
        total_size_mb = sum(p.stat().st_size for p in csv_paths) / 1024 / 1024
        
        logger.info(f"🚀 Procesamiento paralelo con {self.num_workers} workers")
        logger.info(f"📊 {total_csvs} archivos CSV ({total_size_mb:.1f} MB total)")
        
        # Determinar estrategia: paralelo vs secuencial
        # Para archivos pequeños (<50MB total), secuencial es más eficiente
        use_parallel = total_size_mb > 50 and total_csvs > 1
        
        all_warnings = []
        
        if use_parallel and self.num_workers > 1:
            logger.info(f"⚡ Usando procesamiento PARALELO ({self.num_workers} workers)")
            all_warnings = self._process_parallel(csv_paths, empresas_list, nombre_defecto, progress_callback)
        else:
            logger.info(f"📝 Usando procesamiento SECUENCIAL (archivos pequeños o worker único)")
            all_warnings = self._process_sequential(csv_paths, empresas_list, nombre_defecto, progress_callback)
        
        # Cerrar agregador y obtener nombres de archivos
        logger.info("🔄 Cerrando escritores CSV...")
        nombres = self.aggregator.close()
        counts = self.aggregator.counts
        
        return nombres, all_warnings, counts
    
    def _process_sequential(
        self, 
        csv_paths: List[Path], 
        empresas_list: List[str], 
        nombre_defecto: str,
        progress_callback
    ) -> List[str]:
        """Procesamiento secuencial tradicional (más eficiente para archivos pequeños)"""
        all_warnings = []
        
        for i, csv_path in enumerate(csv_paths, 1):
            file_size_mb = csv_path.stat().st_size / 1024 / 1024
            logger.info(f"📄 [{i}/{len(csv_paths)}] {csv_path.name} ({file_size_mb:.1f} MB)")
            
            if progress_callback:
                progress_callback(csv_path.name, 0, len(csv_paths))
            
            try:
                saw_t1 = saw_t2 = False
                rows_processed = 0
                
                # Usar parser optimizado (PyArrow si disponible)
                for table, es_aj, row, cols, os_name in stream_tables_func(csv_path, empresas_list, nombre_defecto):
                    if table == "t1": saw_t1 = True
                    if table == "t2": saw_t2 = True
                    self.aggregator.add_row(table, es_aj, row, cols, os_name)
                    rows_processed += 1
                    
                    if rows_processed % 50000 == 0 and progress_callback:
                        progress_callback(csv_path.name, rows_processed, len(csv_paths))
                
                logger.info(f"   ✅ {rows_processed:,} filas procesadas")
                
                if not saw_t1:
                    all_warnings.append(f"{csv_path.name}: 'Control Statistics' no encontrada o vacía")
                if not saw_t2:
                    all_warnings.append(f"{csv_path.name}: 'RESULTS' no encontrada o vacía")
                    
            except Exception as ex:
                logger.error(f"❌ Error procesando {csv_path.name}: {ex}")
                all_warnings.append(f"{csv_path.name}: error de parseo: {ex}")
        
        return all_warnings
    
    def _process_parallel(
        self, 
        csv_paths: List[Path], 
        empresas_list: List[str], 
        nombre_defecto: str,
        progress_callback
    ) -> List[str]:
        """
        Procesamiento paralelo usando multiprocessing.
        NOTA: Actualmente deshabilitado para evitar problemas de serialización.
        Usar _process_sequential en su lugar.
        """
        # Por ahora, usar procesamiento secuencial ya que multiprocessing
        # tiene problemas con objetos complejos como CsvAggregator
        logger.warning("⚠️ Procesamiento paralelo no implementado, usando secuencial")
        return self._process_sequential(csv_paths, empresas_list, nombre_defecto, progress_callback)
