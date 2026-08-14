# Play Store App Audit

Utility per controllare in blocco i package Android e ottenere direttamente nell'app:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- stato del listing;
- titolo attuale sullo Store;
- fonte della data di aggiornamento;
- note sui casi problematici o ambigui.

## Novità della GUI

La versione Windows mostra i risultati direttamente in una tabella interna, senza creare automaticamente file di output.

La tabella permette di:

- ordinare i risultati cliccando sulle intestazioni delle colonne;
- filtrare rapidamente le righe con il campo `Filter`;
- vedere il riepilogo di app disponibili e casi da controllare;
- fare doppio clic su una riga per aprire il listing Play Store;
- esportare il CSV soltanto quando serve, tramite `Export results…`.

## Esclusione delle system app

La casella:

`Exclude system apps (phone scans and CSV files)`

è attiva di default e vale sia per la scansione diretta del telefono sia per i file CSV/TXT caricati.

### Se analizzi direttamente il telefono

Premi `Scan phone with ADB`.

L'app legge tutti i package e separa quelli di sistema usando ADB. La classificazione è quindi riferita al telefono effettivamente collegato. Puoi cambiare il checkbox anche dopo la scansione e prima di avviare l'audit.

### Se carichi un CSV / TSV / TXT

Prima dell'audit, il programma prova a identificare le system app in questo ordine:

1. usa eventuali colonne del file come `is_system`, `system_app`, `system` o `app_type`;
2. se è collegato e autorizzato un telefono Android via ADB, confronta i package del file con `adb shell pm list packages -s`, ottenendo una classificazione esatta per quel telefono;
3. se non sono disponibili né metadati né ADB, applica solo un fallback prudente sui package chiaramente di sistema.

Le app classificate come system vengono rimosse **prima** di interrogare il Play Store, quindi non consumano richieste dell'audit.

Per una classificazione affidabile di un CSV che non contiene un flag di sistema, il metodo migliore è collegare lo stesso telefono da cui proviene la lista e lasciare ADB disponibile.

## Analisi diretta del telefono

Premi `Scan phone with ADB` per leggere direttamente le app installate dal telefono, senza creare prima un CSV intermedio.

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

Per indicare esplicitamente se una riga è una system app, puoi aggiungere per esempio una colonna `is_system` con valori `true/false`, `1/0`, `yes/no`, `system/user`.

## File principali

- `playstore_audit_core.py`: motore dell'audit
- `playstore_audit_gui.py`: interfaccia Windows
- `playstore_audit_cli.py`: versione command line
- `playstore_audit_final_colab.ipynb`: versione Colab
- `.github/workflows/build-windows-exe.yml`: build online Windows
- `requirements.txt`: dipendenze
- `extract_packages_from_phone.ps1`: esportazione package da Android, se vuoi ancora usare il metodo manuale
