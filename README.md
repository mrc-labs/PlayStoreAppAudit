# Play Store App Audit

Utility per controllare in blocco i package Android e ottenere direttamente nell'app:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- stato del listing;
- titolo attuale sullo Store;
- fonte della data di aggiornamento;
- note sui casi problematici o ambigui.

## Novità della GUI

La versione Windows mostra ora i risultati direttamente in una tabella interna, senza creare automaticamente file di output.

La tabella permette di:

- ordinare i risultati cliccando sulle intestazioni delle colonne;
- filtrare rapidamente le righe con il campo `Filter`;
- vedere il riepilogo di app disponibili e casi da controllare;
- fare doppio clic su una riga per aprire il listing Play Store;
- esportare il CSV soltanto quando serve, tramite `Export results…`.

## Analisi diretta del telefono

Premi `Scan phone with ADB` per leggere direttamente le app installate dal telefono, senza creare prima un CSV intermedio.

La casella:

`Exclude system apps when scanning phone`

è attiva di default.

- attiva: usa `adb shell pm list packages -3` e analizza le app di terze parti;
- disattiva: usa `adb shell pm list packages` e include anche i package di sistema.

Dopo la scansione, la lista resta in memoria e puoi premere `Run Play Store audit`.

## Creare l'EXE Windows online

Il repository contiene:

`.github/workflows/build-windows-exe.yml`

Il workflow GitHub Actions gira su un runner Windows e genera `PlayStoreAppAudit.exe` come artifact.

Ogni modifica a `playstore_audit_gui.py`, `playstore_audit_core.py`, `requirements.txt` o al workflow avvia automaticamente una nuova build.

## Altri metodi

### Google Colab

Usa `playstore_audit_final_colab.ipynb` se vuoi eseguire l'audit online senza usare l'EXE.

### Python su Windows

Doppio clic su:

`run_windows_gui.bat`

### Build locale Windows

Doppio clic su:

`build_windows_exe.bat`

## Input file supportati

Se preferisci non usare ADB direttamente, puoi caricare:

- CSV;
- TSV;
- TXT;
- output ADB `package:com.example.app`.

Sono riconosciute colonne come:

- `package_name`
- `package`
- `packageName`
- `packageId`
- `app_id`
- `id`

Il nome dell'app è opzionale.

## File principali

- `playstore_audit_core.py`: motore dell'audit
- `playstore_audit_gui.py`: interfaccia Windows
- `playstore_audit_cli.py`: versione command line
- `playstore_audit_final_colab.ipynb`: versione Colab
- `.github/workflows/build-windows-exe.yml`: build online Windows
- `requirements.txt`: dipendenze
- `extract_packages_from_phone.ps1`: esportazione package da Android, se vuoi ancora usare il metodo manuale
