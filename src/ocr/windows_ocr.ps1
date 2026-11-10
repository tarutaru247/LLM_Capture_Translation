param([Parameter(Mandatory=$true)][string]$ImagePath, [string]$Language = 'en')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] > $null
    [Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime] > $null
    [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] > $null
    [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] > $null
    [Windows.Storage.Streams.DataWriter, Windows.Storage.Streams, ContentType=WindowsRuntime] > $null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] > $null
    [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] > $null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] > $null
    [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] > $null
    [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] > $null
    $script:asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    function Await-Operation($operation, [Type]$resultType) {
        $task = $script:asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
        return $task.GetAwaiter().GetResult()
    }
    if ($Language -eq 'auto') {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    } else {
        $lang = New-Object Windows.Globalization.Language($Language)
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    }
    if ($null -eq $engine) {
        @{error='language_missing'; languages=@([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag })} | ConvertTo-Json -Compress
        exit 2
    }
    # Desktop file I/O avoids StorageFile broker restrictions on portable/network drives.
    $bytes = [System.IO.File]::ReadAllBytes($ImagePath)
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $writer = New-Object Windows.Storage.Streams.DataWriter($stream)
    try {
        $writer.WriteBytes($bytes)
        Await-Operation ($writer.StoreAsync()) ([uint32]) > $null
        $writer.DetachStream() > $null
    } finally { $writer.Dispose() }
    $stream.Seek(0)
    try {
        $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        try {
            $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            @{text=(@($result.Lines | ForEach-Object { $_.Text }) -join "`n"); language=$engine.RecognizerLanguage.LanguageTag} | ConvertTo-Json -Compress
        } finally { $bitmap.Dispose() }
    } finally { $stream.Dispose() }
} catch {
    # Do not emit the screenshot, its path, or exception details to logs.
    @{error='ocr_failed'} | ConvertTo-Json -Compress
    exit 1
}
