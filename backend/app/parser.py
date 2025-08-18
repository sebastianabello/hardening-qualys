from __future__ import annotations
from pathlib import Path
from typing import Iterator, Tuple, Dict, Any
import csv
import io
import zipfile

# Parseo robusto de reportes Qualys (CSV o ZIP con CSVs) sin esquema fijo.
# Reglas clave:
#  - Tabla 1: detectar el encabezado "Control Statistics"; la línea inmediatamente siguiente define columnas.
#  - Tabla 2: detectar el marcador "RESULTS"; la línea siguiente define columnas.
#  - Añadir columna "Cliente" con el nombre de cliente proporcionado (o por defecto) en todos los documentos.

Markers = {
    "control": "Control Statistics",
    "results": "RESULTS",
}

class QualysParser:
    def __init__(self, client: str, run_id: str) -> None:
        self.client = client or "DEFAULT"
        self.run_id = run_id
        self.manifest_docs: list[dict[str, Any]] = []
        self.error_docs: list[dict[str, Any]] = []

    def parse_input(self, path: Path) -> Tuple[list[dict], list[dict]]:
        control_rows: list[dict] = []
        result_rows: list[dict] = []

        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path, "r") as z:
                for name in z.namelist():
                    if not name.lower().endswith(".csv"):  # ignorar no-CSV
                        continue
                    data = z.read(name)
                    control, results = self._parse_csv_bytes(data, source=f"{path.name}:{name}")
                    control_rows.extend(control)
                    result_rows.extend(results)
                    self._add_manifest_entry(path.name, name, len(data))
        else:
            data = path.read_bytes()
            control, results = self._parse_csv_bytes(data, source=path.name)
            control_rows.extend(control)
            result_rows.extend(results)
            self._add_manifest_entry(path.name, None, len(data))

        return control_rows, result_rows

    def _add_manifest_entry(self, archive: str, member: str | None, size_bytes: int) -> None:
        self.manifest_docs.append({
            "type": "source_file",
            "archive": archive,
            "member": member,
            "size_bytes": size_bytes,
            "run_id": self.run_id,
            "Cliente": self.client,
        })

    def _parse_csv_bytes(self, data: bytes, source: str) -> Tuple[list[dict], list[dict]]:
        # Manejar BOM y asegurar texto
        text = data.decode("utf-8-sig", errors="replace")
        lines = io.StringIO(text)

        control_rows: list[dict] = []
        result_rows: list[dict] = []

        # Vamos leyendo línea a línea para detectar marcadores y luego usar csv.DictReader
        buffer: list[str] = []
        mode: str | None = None  # 'control' o 'results'
        headers: list[str] | None = None

        def flush_buffer_to_rows():
            nonlocal buffer, headers, mode, control_rows, result_rows
            if not headers or not mode or not buffer:
                buffer = []
                return
            # Usa csv.DictReader sobre el bloque acumulado
            reader = csv.DictReader(io.StringIO("\n".join([",".join(headers)] + buffer)))
            for i, row in enumerate(reader):
                # Filtrar filas vacías
                if not any((v or "").strip() for v in row.values()):
                    continue
                doc = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                doc["Cliente"] = self.client
                doc["run_id"] = self.run_id
                doc["source"] = source
                if mode == "control":
                    control_rows.append(doc)
                elif mode == "results":
                    result_rows.append(doc)
            buffer = []

        for raw_line in lines:
            line = raw_line.strip("\n\r")
            # Detección de marcadores exactos o entrecomillados (primera celda)
            first_cell = next(csv.reader([line]))[0] if line else ""
            normalized = first_cell.strip().strip('"').upper()

            if normalized == Markers["control"].upper():
                # Flushear cualquier bloque anterior
                flush_buffer_to_rows()
                mode = "control"
                headers = None
                continue

            if normalized == Markers["results"].upper():
                flush_buffer_to_rows()
                mode = "results"
                headers = None
                continue

            # Si estamos justo después de un marcador, la primera línea no vacía es el header
            if mode and headers is None:
                if line.strip() == "":
                    continue
                headers = [h.strip().strip('"') for h in next(csv.reader([line]))]
                # Normalizar nombres de columnas duplicadas o vacías
                seen: dict[str, int] = {}
                norm_headers: list[str] = []
                for h in headers:
                    key = h or "col"
                    count = seen.get(key, 0)
                    seen[key] = count + 1
                    norm_headers.append(key if count == 0 else f"{key}_{count}")
                headers = norm_headers
                continue

            # Estamos dentro de un bloque, acumulamos líneas hasta que venga un marcador o un separador fuerte
            if mode and headers:
                # Un separador fuerte puede ser línea vacía que detiene la tabla
                if line.strip() == "":
                    flush_buffer_to_rows()
                    mode = None
                    headers = None
                else:
                    buffer.append(line)
            else:
                # Líneas fuera de bloques: ignorar
                continue

        # Fin de archivo: flushear
        flush_buffer_to_rows()

        return control_rows, result_rows
