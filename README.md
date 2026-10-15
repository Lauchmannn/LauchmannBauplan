# Lauchmann Bauplan 0.2

Lokaler Minecraft-Bauplan-Viewer für **`.litematic`-Dateien**.

## Start

1. Python 3 installieren.
2. `start.bat` doppelklicken.
3. Der Browser öffnet `http://127.0.0.1:8770/`.

## Was diese Version kann

- `.litematic` direkt im Browser importieren
- 3D-Gesamtansicht
- Schnitt bis zu einer Y-Ebene
- einzelne Y-Ebene
- Draufsicht
- Block anklicken: Block-ID + exakte Blockstates
- Materialliste für Ebene oder komplettes Bauwerk
- Stacks in der Materialliste
- Ebenen als fertig markieren; Fortschritt bleibt lokal im Browser
- Rendering nur bei Änderungen statt in einer permanenten 60-FPS-Schleife
- Oberflächenmodus für die Gesamtansicht, um große Bauwerke leichter zu rendern

## Lokale Daten

Diese Ordner werden bei automatischen Updates niemals überschrieben:

- `projects/`
- `schematics/`
- `user-data/`
- `worlds/`
- `local/`

## Automatische Updates über GitHub

`start.bat` startet zuerst `updater.py`. Sobald dieses Projekt im Repository
`Lauchmannn/LauchmannBauplan` liegt, vergleicht der Updater die lokale `VERSION`
mit der Version auf GitHub und lädt neue Programmdateien automatisch.

Die lokalen Litematics und Baufortschritte werden dabei nicht verändert.
