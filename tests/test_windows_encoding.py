"""Prevent Windows installer text from reverting to the wrong character set.

Inno Setup 6.2.x requires UTF-8 *with BOM* to read Spanish accents correctly.
The script intentionally mentions old mangled shortcut names only to delete them.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "windows" / "Moimetro.iss"


def test_inno_script_requires_utf8_bom_and_spanish_names():
    raw = SCRIPT.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), (
        "Inno Setup 6.2.x necesita BOM UTF-8 para conservar la í de Moímetro."
    )
    source = raw.decode("utf-8-sig")
    assert '#define MyAppName "Moímetro"' in source
    assert "AppName={#MyAppName}" in source
    assert "DefaultGroupName={#MyAppName}" in source
    assert 'Name: "{autodesktop}\\Moímetro"' in source
    assert 'Name: "{autoprograms}\\Moímetro"' in source
    assert 'Description: "Iniciar Moímetro"' in source
    # Old shortcuts are removed when upgrading rather than lingering on desktop.
    assert '[InstallDelete]' in source
    assert 'MoÃ\u00admetro.lnk' in source


def test_no_mojibake_in_user_interface_or_launcher():
    for path in (ROOT / "app" / "static").glob("*"):
        if path.suffix not in {".html", ".css", ".js"}:
            continue
        source = path.read_text(encoding="utf-8")
        assert all(garbled not in source for garbled in ("MoÃ", "Â¡", "Â¿", "â€™", "�")), path
    launcher = (ROOT / "app" / "launcher.py").read_text(encoding="utf-8")
    assert '"Moímetro"' in launcher
    assert "MoÃ" not in launcher
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert '<meta charset="UTF-8">' in html
