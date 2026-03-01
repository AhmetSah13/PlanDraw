from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


class DwgConversionError(Exception):
    """DWG -> DXF dönüşüm hatası için özel istisna."""


def _get_converter_command(input_path: Path, output_path: Path) -> list[str]:
    """
    Ortam değişkenlerinden DWG dönüştürücü komutunu oluşturur.

    DWG_CONVERTER_PATH: Çalıştırılabilir dosya yolu.
    DWG_CONVERTER_ARGS: Argüman şablonu, {input} ve {output} placeholder'larını içerebilir.
        Örnek: "--in {input} --out {output}" veya "{input} {output}"
    """
    converter_path = os.getenv("DWG_CONVERTER_PATH")
    if not converter_path:
        raise DwgConversionError(
            "DWG conversion not configured. Please upload DXF or export DWG to DXF."
        )

    args_template = os.getenv("DWG_CONVERTER_ARGS") or "{input} {output}"
    formatted = args_template.format(
        input=str(input_path),
        output=str(output_path),
    )
    argv = [converter_path]
    if formatted.strip():
        argv.extend(shlex.split(formatted))
    return argv


def convert_dwg_bytes_to_dxf_text(dwg_bytes: bytes, timeout_seconds: float = 60.0) -> str:
    """
    Verilen DWG baytlarını geçici dizine yazar, harici dönüştürücü ile DXF'e çevirir
    ve UTF-8 olarak okunmuş DXF metnini döndürür.
    """
    if not isinstance(dwg_bytes, (bytes, bytearray)):
        raise DwgConversionError("DWG verisi bytes olmalıdır.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_path = tmpdir_path / "input.dwg"
        output_path = tmpdir_path / "output.dxf"

        input_path.write_bytes(dwg_bytes)

        cmd = _get_converter_command(input_path, output_path)

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise DwgConversionError("DWG dönüştürme zaman aşımına uğradı.") from exc
        except OSError as exc:
            # Örneğin çalıştırılabilir bulunamadı.
            raise DwgConversionError(f"DWG dönüştürücü çalıştırılamadı: {exc!s}") from exc

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
            raise DwgConversionError(f"DWG dönüştürme başarısız: {err_msg}")

        if not output_path.exists():
            raise DwgConversionError("DWG dönüştürme DXF çıktısı üretmedi.")

        try:
            dxf_text = output_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            # Şu an: metin değilse reddet. İleride istenirse utf-8 fail → latin-1 gibi
            # "best effort" modu eklenebilir (bazı converter'lar ANSI/CP1254 verebilir).
            raise DwgConversionError("DXF çıktısı geçerli UTF-8 metin değil.") from exc

        if not dxf_text.strip():
            raise DwgConversionError("DXF çıktısı boş.")

        return dxf_text

