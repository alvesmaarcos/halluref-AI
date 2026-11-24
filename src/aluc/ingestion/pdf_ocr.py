"""Reconhecimento de texto local em PDFs digitalizados no Windows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


_WINDOWS_OCR = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Data.Pdf.PdfDocument,Windows.Data.Pdf,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$methods = [System.WindowsRuntimeSystemExtensions].GetMethods()
$asTask = $methods | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
}
$asActionTask = $methods | Where-Object {
    $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
}
function Await-Result($operation, [Type] $type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($operation))
    $task.GetAwaiter().GetResult()
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { throw 'No Windows OCR language is installed.' }
$file = [System.IO.File]::OpenRead($env:ALUC_OCR_PDF)
$inputStream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($file)
$pdf = Await-Result ([Windows.Data.Pdf.PdfDocument]::LoadFromStreamAsync($inputStream)) ([Windows.Data.Pdf.PdfDocument])

$pages = for ($index = 0; $index -lt $pdf.PageCount; $index++) {
    $page = $pdf.GetPage($index)
    $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
    try {
        $options = [Windows.Data.Pdf.PdfPageRenderOptions]::new()
        $scale = [Math]::Min(2.5, [Windows.Media.Ocr.OcrEngine]::MaxImageDimension /
                                [Math]::Max($page.Size.Width, $page.Size.Height))
        $options.DestinationWidth = [uint32][Math]::Floor($page.Size.Width * $scale)
        $action = $page.RenderToStreamAsync($stream, $options)
        $null = $asActionTask.Invoke($null, @($action)).GetAwaiter().GetResult()
        $stream.Seek(0)
        $decoder = Await-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        try {
            $result = Await-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            $lines = @($result.Lines | ForEach-Object {
                $word = $_.Words | Select-Object -First 1
                $box = $word.BoundingRect
                [PSCustomObject]@{
                    Text = $_.Text
                    X = [double]@($box.X)[0]
                    Y = [double]@($box.Y)[0]
                    Height = [double]@($box.Height)[0]
                }
            })
            # OCR occasionally reads the numbering gutter as a separate column.
            foreach ($marker in $lines) {
                if ($marker.Text -notmatch '^(?:\[[0-9Il|O]+[\]J)]?|1[0-9Il|O]{1,4}[\]J)])$') { continue }
                $candidate = $lines | Where-Object {
                    $_.X -gt $marker.X -and $_.Text -match '^[^\W\d_]' -and
                    [Math]::Abs($_.Y - $marker.Y) -le $marker.Height * 0.5
                } | Sort-Object X | Select-Object -First 1
                if ($candidate) {
                    $candidate.Text = $marker.Text + ' ' + $candidate.Text
                    $marker.Text = ''
                }
            }
            ($lines | ForEach-Object { $_.Text } | Where-Object { $_ }) -join [char]10
        } finally {
            $bitmap.Dispose()
        }
    } finally {
        $stream.Dispose()
        $page.Dispose()
    }
}
ConvertTo-Json -InputObject @($pages) -Compress
"""


def recognize_pdf(path: Path) -> list[str]:
    """Extrai texto por página sem enviar o PDF a um serviço externo."""
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_OCR],
            env={**os.environ, "ALUC_OCR_PDF": str(path.resolve())},
            capture_output=True,
            encoding="utf-8",
            timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # WinRT can fail during process teardown after writing the complete JSON.
        pages = json.loads(result.stdout)
        if isinstance(pages, list) and all(isinstance(page, str) for page in pages):
            return pages
        return []
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def recognize_pdf_bytes(data: bytes) -> list[str]:
    if os.name != "nt":
        return []
    with tempfile.TemporaryDirectory(prefix="aluc-ocr-") as directory:
        path = Path(directory) / "document.pdf"
        path.write_bytes(data)
        return recognize_pdf(path)
