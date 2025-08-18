from pathlib import Path
from typing import Dict, Tuple
import httpx
from openpyxl import load_workbook
from .config import settings

def _bulk_iter_lines(index: str, rows_iter):
    action = f'{{"index":{{"_index":"{index}"}}}}'
    for doc in rows_iter:
        yield action
        yield doc

from typing import Iterator

def _iter_excel_docs(xlsx_path: Path) -> Iterator[str]:
    """
    Lee un xlsx en modo read-only.
    Devuelve: (doc_json_line) como strings para _bulk.
    """
    import json
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers:
        wb.close()
        return
    headers = [str(h) if h is not None else "" for h in headers]
    for values in rows:
        obj = {}
        for i, h in enumerate(headers):
            obj[h] = "" if values is None or i >= len(values) or values[i] is None else values[i]
        yield json.dumps(obj, ensure_ascii=False)
    wb.close()

def _guess_targets(xlsx_name: str) -> Tuple[str, bool]:
    """
    Determina índice destino y flag ajustada a partir del nombre de archivo.
    """
    name = xlsx_name.lower()
    es_control = "-control-statics" in name
    ajustada = "-ajustado" in name
    index = settings.ES_INDEX_CONTROL if es_control else settings.ES_INDEX_RESULTS
    return index, ajustada

async def ingest_run_folder(run_output_dir: Path) -> Dict[str, int]:
    """
    Recorre los xlsx del run y los envia por _bulk al índice correspondiente.
    Añade campo 'ajustada' en el documento, si no existe.
    Devuelve conteo por índice.
    """
    import json

    count_by_index: Dict[str, int] = {}
    async with httpx.AsyncClient(timeout=120.0) as client:
        headers = {"Content-Type": "application/x-ndjson"}
        if settings.ES_API_KEY:
            headers["Authorization"] = f"ApiKey {settings.ES_API_KEY}"

        for x in sorted(run_output_dir.glob("*.xlsx")):
            index, ajustada = _guess_targets(x.name)

            # Construir buffer por lotes (para no saturar memoria)
            buf_lines = []
            buf_bytes = 0
            sent = 0

            def flush_sync():
                nonlocal buf_lines, buf_bytes, sent
                if not buf_lines:
                    return
                data = ("\n".join(buf_lines) + "\n").encode("utf-8")
                resp = client.post(f"{settings.ES_BASE_URL}/_bulk", content=data, headers=headers)
                res = resp.json()
                if res.get("errors"):
                    # No reventamos, pero reportamos errores (front lo mostrará)
                    pass
                items = res.get("items", [])
                sent += sum(1 for it in items if "index" in it and 200 <= it["index"].get("status", 500) < 300)
                buf_lines = []; buf_bytes = 0

            # Consume documentos
            import json as _json
            for doc_line in _iter_excel_docs(x):
                # inyectar 'ajustada' si no existe
                d = _json.loads(doc_line)
                if "ajustada" not in d:
                    d["ajustada"] = ajustada
                doc_line = _json.dumps(d, ensure_ascii=False)

                # preparar acción + doc
                buf_lines.append(f'{{"index":{{"_index":"{index}"}}}}')
                buf_lines.append(doc_line)
                buf_bytes += len(buf_lines[-1]) + len(buf_lines[-2]) + 2

                if buf_bytes >= 5_000_000 or len(buf_lines) >= 10_000:
                    flush_sync()

            flush_sync()
            count_by_index[index] = count_by_index.get(index, 0) + sent

    return count_by_index
