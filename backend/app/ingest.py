from __future__ import annotations
from pathlib import Path
import csv
from typing import Dict, Iterator
import json
import httpx
from openpyxl import load_workbook
from .config import settings
from itertools import chain

def _iter_csv_docs(csv_path: Path):
    import json
    with csv_path.open("r", encoding="utf-8", newline="", errors="ignore") as f:
        rdr = csv.reader(f)
        headers = next(rdr, None)
        if not headers:
            return
        headers = [str(h) if h is not None else "" for h in headers]
        for row in rdr:
            obj = {}
            for i, h in enumerate(headers):
                obj[h] = "" if i >= len(row) or row[i] is None else row[i]
            yield json.dumps(obj, ensure_ascii=False)


def _iter_excel_docs(xlsx_path: Path) -> Iterator[str]:
    """
    Itera filas de un XLSX (read-only) y devuelve cada fila como JSON (str).
    """
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        headers = next(rows, None)
        if not headers:
            return
        headers = [str(h) if h is not None else "" for h in headers]
        for values in rows:
            obj = {}
            for i, h in enumerate(headers):
                obj[h] = "" if values is None or i >= len(values) or values[i] is None else values[i]
            yield json.dumps(obj, ensure_ascii=False)
    finally:
        wb.close()


def _guess_targets(xlsx_name: str) -> tuple[str, bool]:
    """
    Determina índice destino y flag 'ajustada' por el nombre del archivo.
    """
    name = xlsx_name.lower()
    es_control = "-control-statics" in name
    ajustada = "-ajustado" in name
    index = settings.ES_INDEX_CONTROL if es_control else settings.ES_INDEX_RESULTS
    return index, ajustada


async def ingest_run_folder(run_output_dir: Path) -> Dict[str, int]:
    """
    Recorre los XLSX del run y los ingesta en ES vía _bulk, por lotes.
    Devuelve conteo por índice.
    """
    count_by_index: Dict[str, int] = {}

    headers = {"Content-Type": "application/x-ndjson"}
    if settings.ES_API_KEY:
        headers["Authorization"] = f"ApiKey {settings.ES_API_KEY}"

    # Si quieres soportar TLS no verificado, añade verify=settings.ES_VERIFY_TLS en config
    async with httpx.AsyncClient(timeout=120.0) as client:
        files = list(chain(sorted(run_output_dir.glob("*.xlsx")),
                           sorted(run_output_dir.glob("*.csv"))))

        for x in files:
            index, ajustada = _guess_targets(x.name)

            if x.suffix.lower() == ".csv":
                iter_docs = _iter_csv_docs(x)
            else:
                iter_docs = _iter_excel_docs(x)

            buf_lines = []
            buf_bytes = 0
            sent = 0

            async def flush():
                nonlocal buf_lines, buf_bytes, sent
                if not buf_lines:
                    return
                data = ("\n".join(buf_lines) + "\n").encode("utf-8")
                resp = await client.post(f"{settings.ES_BASE_URL}/_bulk", content=data, headers=headers)
                resp.raise_for_status()
                res = resp.json()
                items = res.get("items", [])
                sent += sum(1 for it in items if "index" in it and 200 <= it["index"].get("status", 500) < 300)
                buf_lines, buf_bytes = [], 0

            for doc_line in iter_docs:
                d = json.loads(doc_line)
                if "ajustada" not in d:
                    d["ajustada"] = ajustada
                doc_line = json.dumps(d, ensure_ascii=False)

                buf_lines.append(json.dumps({"index": {"_index": index}}, ensure_ascii=False))
                buf_lines.append(doc_line)
                buf_bytes += len(buf_lines[-1]) + len(buf_lines[-2]) + 2

                if buf_bytes >= 5_000_000 or len(buf_lines) >= 10_000:
                    await flush()

            await flush()
            count_by_index[index] = count_by_index.get(index, 0) + sent

    return count_by_index
