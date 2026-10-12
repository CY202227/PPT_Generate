param(
    [Parameter(Mandatory = $true)][string]$PptxPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$resolvedPptx = (Resolve-Path -LiteralPath $PptxPath).Path
$previewDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $previewDirectory | Out-Null
$existingProcesses = @(Get-Process -Name POWERPNT -ErrorAction SilentlyContinue)
$powerPoint = $null
$presentation = $null
$issues = [Collections.Generic.List[object]]::new()
$pages = [Collections.Generic.List[object]]::new()

function Measure-Text($shape, [int]$page, [string]$name, $rectangles, [bool]$recordOverlap = $true) {
    if ($shape.HasTextFrame -ne -1 -or -not $shape.TextFrame2.TextRange.Text.Trim()) { return }
    $frame = $shape.TextFrame2
    $range = $frame.TextRange
    $availableHeight = $shape.Height - $frame.MarginTop - $frame.MarginBottom
    $availableWidth = $shape.Width - $frame.MarginLeft - $frame.MarginRight
    if ($range.BoundHeight -gt $availableHeight + 1.5 -or $range.BoundWidth -gt $availableWidth + 1.5) {
        $issues.Add(@{ page = $page; code = 'text_overflow'; object = $name; bound_height_pt = [Math]::Round($range.BoundHeight, 2); available_height_pt = [Math]::Round($availableHeight, 2); bound_width_pt = [Math]::Round($range.BoundWidth, 2); available_width_pt = [Math]::Round($availableWidth, 2) })
    }
    if ($recordOverlap) {
        $rectangles.Add(@{ name = $name; x = [double]$range.BoundLeft; y = [double]$range.BoundTop; w = [double]$range.BoundWidth; h = [double]$range.BoundHeight })
    }
}

try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerPoint.Presentations.Open($resolvedPptx, -1, 0, 0)
    $slideWidth = $presentation.PageSetup.SlideWidth
    $slideHeight = $presentation.PageSetup.SlideHeight
    for ($page = 1; $page -le $presentation.Slides.Count; $page++) {
        $slide = $presentation.Slides.Item($page)
        $fileName = 'slide-{0:D3}.png' -f $page
        $slide.Export((Join-Path $previewDirectory $fileName), 'PNG', 1600, 900)
        $rectangles = [Collections.Generic.List[object]]::new()
        foreach ($shape in $slide.Shapes) {
            if ($shape.Left -lt -1 -or $shape.Top -lt -1 -or $shape.Left + $shape.Width -gt $slideWidth + 1 -or $shape.Top + $shape.Height -gt $slideHeight + 1) {
                $issues.Add(@{ page = $page; code = 'object_out_of_bounds'; object = $shape.Name })
            }
            Measure-Text $shape $page $shape.Name $rectangles
            if ($shape.HasTable -eq -1) {
                for ($row = 1; $row -le $shape.Table.Rows.Count; $row++) {
                    for ($column = 1; $column -le $shape.Table.Columns.Count; $column++) {
                        # Cell text bounds are local to the cell, not slide coordinates.
                        # Check cell overflow, but compare overlap only among global textboxes.
                        Measure-Text ($shape.Table.Cell($row, $column).Shape) $page ($shape.Name + ':' + $row + ':' + $column) $rectangles $false
                    }
                }
            }
        }
        for ($a = 0; $a -lt $rectangles.Count; $a++) {
            for ($b = $a + 1; $b -lt $rectangles.Count; $b++) {
                $first = $rectangles[$a]; $second = $rectangles[$b]
                $overlapWidth = [Math]::Min($first.x + $first.w, $second.x + $second.w) - [Math]::Max($first.x, $second.x)
                $overlapHeight = [Math]::Min($first.y + $first.h, $second.y + $second.h) - [Math]::Max($first.y, $second.y)
                if ($overlapWidth -gt 2 -and $overlapHeight -gt 2) {
                    $issues.Add(@{ page = $page; code = 'text_overlap'; objects = @($first.name, $second.name) })
                }
            }
        }
        $pages.Add(@{ page = $page; file = $fileName; measured_overlap_textboxes = $rectangles.Count })
    }
    $status = if ($issues.Count -eq 0) { 'passed' } else { 'issues_found' }
    $report = @{ backend = 'powerpoint'; engine_version = $powerPoint.Version; status = $status; pages = @($pages.ToArray()); issues = @($issues.ToArray()); scope = 'actual text capacity for textboxes/table cells, textbox ink overlap, object slide bounds'; limitations = @('Chart-internal labels, cell-to-cell ink overlap and aesthetic/factual quality are not certified'); visual_review = 'required' }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $previewDirectory 'report.json') -Encoding UTF8
} finally {
    if ($null -ne $presentation) {
        $presentation.Close()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
    }
    if ($null -ne $powerPoint) {
        # Do not quit an application instance that the user already had open.
        if ($existingProcesses.Count -eq 0 -and $powerPoint.Presentations.Count -eq 0) { $powerPoint.Quit() }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint)
    }
}
