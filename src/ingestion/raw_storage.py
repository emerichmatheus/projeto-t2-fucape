"""Camada Raw/Bronze em arquivos JSONL particionados por data de ingestão.

Idempotência: cada (ingest_date, app_id) corresponde a UM arquivo. A escrita
vai para um arquivo temporário no mesmo diretório e depois é renomeada de
forma atômica (``os.replace``), sobrescrevendo a partição. Reexecutar o mesmo
``ds`` substitui o arquivo em vez de acumular linhas duplicadas, e uma falha
no meio da escrita nunca deixa um arquivo pela metade.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable


def partition_dir(base: Path, ingest_date: str) -> Path:
    return Path(base) / f"ingest_date={ingest_date}"


def _atomic_write(path: Path, lines: Iterable[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line)
                fh.write("\n")
                count += 1
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return count


def write_jsonl_atomic(path: Path, records: Iterable[dict]) -> int:
    return _atomic_write(
        Path(path), (json.dumps(r, ensure_ascii=False) for r in records)
    )


def write_json_atomic(path: Path, obj: dict) -> None:
    _atomic_write(Path(path), [json.dumps(obj, ensure_ascii=False)])


def read_jsonl(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def latest_partition(base: Path) -> str | None:
    """Data da partição mais recente disponível (ou None)."""
    base = Path(base)
    if not base.exists():
        return None
    dates = sorted(
        p.name.split("=", 1)[1] for p in base.iterdir()
        if p.is_dir() and p.name.startswith("ingest_date=")
    )
    return dates[-1] if dates else None
