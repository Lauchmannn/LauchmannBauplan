# Lauchmann Bauplan

Windows-lokaler Minecraft-Bauplan-Viewer für **`.litematic`-Dateien**. Import, Konvertierung und Darstellung bleiben auf deinem Rechner. Keine Weltmap, kein Cloud-Konto und keine mitgelieferten Bauwerke.

## Start unter Windows

1. **Python 3.10 oder neuer** von [python.org](https://www.python.org/downloads/windows/) installieren (Python-Launcher bzw. „Add Python to PATH“ aktivieren).
2. Repository herunterladen/entpacken oder klonen.
3. `start.bat` doppelklicken. Keine zusätzlichen Python-Pakete nötig.
4. Der Browser öffnet `http://127.0.0.1:8770`. Falls nicht, diese Adresse manuell öffnen.
5. `.litematic` auswählen oder ins Fenster ziehen. Chrome, Edge oder Firefox mit **WebGL 2** verwenden.

Das Konsolenfenster offen lassen; zum Beenden Strg+C drücken. Port 8770 muss frei sein. Alternativ, auch unter Linux/macOS: im Projektverzeichnis `python server.py` (bzw. `python3 server.py`) ausführen. Der Server bindet ausschließlich an `127.0.0.1`, ohne Internetdienste oder externe JavaScript-Abhängigkeiten. Der Start verändert keine Programmdateien und führt den alten `updater.py` nicht aus; Updates erfolgen bewusst über Git bzw. einen neuen Download.

## Bedienung

- Links ziehen: drehen; rechts ziehen: verschieben; Mausrad: zoomen; „Ansicht zentrieren“: Kamera zurücksetzen.
- „3D“ / „Draufsicht“ wechseln die Kamera.
- „Gesamt“, „Nur Ebene“ und „Schnitt bis Y“ wählen den sichtbaren Teil. Schnitt enthält die ausgewählte Ebene.
- Y-Regler und −/+ wechseln Ebenen von unten nach oben. Angezeigt wird die ursprüngliche, schemarelative Y-Koordinate. Negative Regionsgrößen werden von der minimalen Ecke aus gelesen, ohne Spiegelung oder umgedrehte Y-Achse.
- Ältere Importe mit möglicherweise vertauschtem Oben/Unten werden beim Öffnen automatisch aus der gespeicherten Originaldatei neu berechnet. Originaldatei, Projektkennung und gespeicherter Fortschritt bleiben erhalten. Fehlt die Originaldatei, fordert ein Hinweis zum erneuten Import auf.
- Block anklicken: Block-ID, exakte Properties und ursprüngliche schemarelative X/Y/Z-Koordinaten (einschließlich Regionsversatz).
- „Materialien“ zeigt die aktuelle Ebene oder das gesamte Bauwerk. Mengen zählen platzierte Blöcke; „Stacks“ sind rechnerische 64er-Gruppen, keine detaillierte Crafting-/Drop-Liste.
- „Ebene fertig“ speichert den Fortschritt pro importiertem Projekt im Browser. Er bleibt beim Neuladen erhalten. Anderes Browserprofil, gelöschter Browserspeicher oder Wechsel von `127.0.0.1` zu `localhost` verwenden einen anderen Speicher. Geänderte Quelldateien erhalten bewusst ein neues Projekt.

## Darstellung und Performance

Die erste Version verwendet eigene Blockstate-abhängige Quader-Modelle für Treppen (Ausrichtung, Hälfte, innere/äußere Ecken), Slabs, Zäune, Mauern, Glasscheiben/Eisengitter, Türen/Falltüren (offen, Ausrichtung, Hälfte), Kakteen, Hopper, Laternen sowie Teppiche, Fackeln, Ketten, Betten und Truhen. Unbekannte Blöcke erscheinen als texturierte Vollblöcke. Das ist eine Minecraft-nahe Annäherung, **kein vollständiger Minecraft-Renderer**: komplexe Mod-/Multipart-Modelle, Blockentities, biomeabhängige Färbung, Flüssigkeitsverbindungen, Beleuchtung und echte transparente Flächen werden noch nicht originalgetreu simuliert. Glas nutzt ausgeschnittene Pixelbereiche; animierte Texturen zeigen das erste Bild.

Vollständig verdeckte Vollblöcke werden beim Import ausgelassen. Der Renderer entfernt verdeckte Nachbarflächen und baut gemeinsame Flächen-Meshes in 16³-Chunks statt ein Objekt bzw. einen vollständigen Würfel pro Block zu zeichnen. Größere Meshes werden in einem Web Worker berechnet. GPU-Picking verwendet dieselben Flächen und Texturausschnitte wie die Darstellung. Es wird nur nach Änderungen gerendert, ohne dauerhafte 60-FPS-Schleife im Leerlauf.

Importgrenzen: 100 MB Quelldatei, 256 MB entpacktes NBT, insgesamt 16 Millionen Regionspositionen, 65535 pro Achse und 65536 verschiedene sichtbare Blockstates. Sehr große oder aus vielen Teilmodellen bestehende Bauwerke benötigen weiterhin viel RAM/GPU-Speicher. Die Materialliste enthält auch unsichtbare innere Blöcke. Überlappende Regionen werden in Dateireihenfolge angewandt, auch wenn eine spätere Region Luft enthält. Entities werden nicht dargestellt.

## Minecraft-Texturen vom eigenen Rechner

Wenn vorhanden, liest der Server PNGs aus der zuletzt geänderten geeigneten Java-Edition-Versions-JAR unter `%APPDATA%\.minecraft\versions\<Version>\<Version>.jar`. Für einen anderen Launcher bzw. eine bestimmte Version vor dem Start setzen:

```bat
set "MINECRAFT_JAR=C:\Pfad\zur\Minecraft-Version.jar"
start.bat
```

Ohne passende lokale Installation werden pro Material erzeugte pixelige Fallback-Texturen verwendet. Im Reiter „Projekt“ steht, wie viele lokale Texturen verwendet werden. Die Zuordnung üblicher Blocktexturen erfolgt pro Seite/Ober-/Unterseite; nicht alle historischen Namen oder Ressourcenpakete werden unterstützt. Es werden **keine Minecraft-Dateien heruntergeladen, extrahiert oder ins Repository kopiert**. Eigene Ressourcenpakete und Minecrafts JSON-Modelle werden bislang nicht geladen.

## Lokale Daten und Git

`schematics/` enthält die importierten Originaldateien, `projects/` die erzeugten JSON-/Binärdaten. Dateiname plus Inhalts-Hash verhindern, dass unterschiedliche Importe mit gleichem Titel einander überschreiben. Ein identischer erneuter Import verwendet dasselbe Projekt. Ungültige Dateien werden nicht dauerhaft übernommen.

`.gitignore` schließt `projects/`, `schematics/`, `user-data/`, `worlds/`, `local/`, `.minecraft/`, `textures-local/`, alle `.litematic`-/`.schem`-/`.schematic`-/`.jar`-Dateien sowie lokale `.env`-Dateien aus. **Diese Daten niemals mit `git add -f` hinzufügen.** Bereits früher getrackte Dateien werden durch `.gitignore` nicht automatisch entfernt; vor jedem öffentlichen Push `git status` und `git diff --cached --stat` kontrollieren. Der HTTP-Server liefert weder Original-Litematics noch Git-Metadaten oder Verzeichnislisten aus. Fortschritt liegt im Browserspeicher und wird nicht mit Git synchronisiert.

## Tests

Im Repositoryverzeichnis:

```sh
python -m unittest discover -s tests -v
node tests/models.test.js
```

Python-Tests prüfen NBT, negative Größen, über 64-Bit-Grenzen gepackte Blockstates, Regionsüberlagerung, Verdeckung, API-Import, Dateischutz und das Lesen lokaler Texturen. Node ist nur für die Modell-/Meshing-Tests nötig.

Optionaler echter Browser-Smoke-Test (isolierte temporäre Daten, keine Änderung eigener Importe):

```sh
python -m pip install playwright
python -m playwright install chromium
python tests/smoke_browser.py
```

Er prüft WebGL, Dateiauswahl und Drag-and-drop, Block-Picking, Ansichten, Ebenen/Materialien, Fortschritt und ausbleibende Renderaufrufe im Leerlauf. Die Windows-Batchdatei muss zusätzlich auf einem Windows-Rechner geprüft werden.
