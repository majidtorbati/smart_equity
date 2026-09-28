$path = ".\app\ui\main_window.py"
$s = Get-Content $path -Raw -Encoding UTF8

$start = $s.IndexOf("        # Concentration")
$end = $s.IndexOf("        # Top players")

if ($start -lt 0 -or $end -lt 0) {
    Write-Host "ERROR - Concentration section not found"
    exit
}

$new = @"
        # ---------------------------------------------------------
        # Concentration
        # ---------------------------------------------------------
        concentration_container = QWidget()

        concentration_layout = QHBoxLayout(concentration_container)
        concentration_layout.setDirection(QBoxLayout.LeftToRight)
        concentration_layout.setSpacing(6)
        concentration_layout.setContentsMargins(0, 0, 0, 0)

        self.buyer_concentration_box = QGroupBox(
            "تمرکز خریداران — Top 1 / 5 / 10"
        )
        self.buyer_concentration_box.setMaximumWidth(520)

        self.buyer_concentration_layout = QVBoxLayout(
            self.buyer_concentration_box
        )
        self.buyer_concentration_layout.addWidget(
            QLabel("خلاصه تمرکز خریداران")
        )

        self.seller_concentration_box = QGroupBox(
            "تمرکز فروشندگان — Top 1 / 5 / 10"
        )
        self.seller_concentration_box.setMaximumWidth(520)

        self.seller_concentration_layout = QVBoxLayout(
            self.seller_concentration_box
        )
        self.seller_concentration_layout.addWidget(
            QLabel("خلاصه تمرکز فروشندگان")
        )

        concentration_layout.addWidget(
            self.seller_concentration_box
        )

        concentration_layout.addWidget(
            self.buyer_concentration_box
        )

        content_layout.addWidget(
            concentration_container,
            0,
            Qt.AlignRight
        )

"@

$s = $s.Substring(0, $start) + $new + $s.Substring($end)

[System.IO.File]::WriteAllText(
    $path,
    $s,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "OK - Concentration fixed"