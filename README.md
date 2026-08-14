# Play Store App Audit - Final

Utility per controllare in blocco i package Android e ottenere:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- stato del listing;
- titolo attuale sullo Store;
- file separato con sole app problematiche.

## Metodo consigliato

### Per creare un EXE Windows online

Leggi `GUIDA_GITHUB_EXE.md`.

Il repository contiene già:

`.github/workflows/build-windows-exe.yml`

Il workflow gira su un runner Windows GitHub e restituisce
`PlayStoreAppAudit.exe` come artifact.

### Per eseguire l'analisi online senza creare un EXE

Usa:

`playstore_audit_final_colab.ipynb`

### Per eseguire l'app da Python su Windows

Doppio clic:

`run_windows_gui.bat`

### Per creare l'EXE localmente su Windows

Doppio clic:

`build_windows_exe.bat`

## Input supportati

- CSV
- TSV
- TXT
- output ADB `package:com.example.app`

Sono riconosciute colonne come:

- package_name
- package
- packageName
- packageId
- app_id
- id

Il nome dell'app è opzionale.

## Estrazione delle app dal telefono

Il metodo preferito usa Android Debug Bridge:

`adb shell pm list packages -3`

Nel pacchetto è presente anche:

`extract_packages_from_phone.ps1`

Consulta `GUIDA_GITHUB_EXE.md` per la procedura completa.

## File principali

- `playstore_audit_core.py`: motore dell'audit
- `playstore_audit_gui.py`: interfaccia Windows
- `playstore_audit_cli.py`: versione command line
- `playstore_audit_final_colab.ipynb`: versione Colab
- `.github/workflows/build-windows-exe.yml`: build online Windows
- `requirements.txt`: dipendenze
- `extract_packages_from_phone.ps1`: esportazione package da Android
- `GUIDA_GITHUB_EXE.md`: guida completa
