# Play Store App Audit

Utility per controllare in blocco i package Android e ottenere direttamente nell'app:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- stato del listing;
- titolo attuale sullo Store;
- fonte della data di aggiornamento;
- classificazione visuale della criticità;
- identificazione delle system app quando possibile.

## Tabella risultati

La versione Windows mostra i risultati direttamente in una tabella interna.

La tabella permette di:

- ordinare i risultati cliccando sulle intestazioni delle colonne;
- filtrare rapidamente le righe con il campo `Filter`;
- nascondere o mostrare le system app senza rieseguire l'audit;
- fare doppio clic su una riga per aprire il listing Play Store;
- esportare il CSV soltanto quando serve, tramite `Export results…`.

### Hide system apps

Il checkbox `Hide system apps` è un filtro puramente visuale.

Tutti i package della sorgente vengono analizzati una sola volta. Dopo l'audit puoi attivare o disattivare il checkbox e la tabella si aggiorna immediatamente.

La classificazione system app usa, in ordine:

1. eventuale colonna CSV come `is_system`, `system`, `system_app` o `app_type`;
2. ADB, se è collegato e autorizzato un telefono Android;
3. un fallback molto prudente basato sui package chiaramente di sistema.

Con una scansione diretta del telefono via ADB la classificazione system/user è esatta per quel dispositivo.

## Criticità e colori

Ogni riga riceve un colore e la colonna finale `Criticality`:

- 🔴 `Removed`: app non più trovata sul Play Store;
- 🟡 `Aging`: ultimo aggiornamento più vecchio di 365 giorni e non oltre 730 giorni;
- 🟠 `Stale`: ultimo aggiornamento più vecchio di 730 giorni;
- 🟢 `Current`: ultimo aggiornamento non più vecchio di 365 giorni;
- 🟣 `Other`: data assente/non interpretabile, errore di richiesta, disponibilità soltanto nel locale fallback o altra situazione non classificabile con sicurezza.

La colonna `Criticality` è ordinabile per severità.

Il riepilogo sopra la tabella mostra anche il numero di righe per ciascun colore e quante system app sono nascoste.

## Analisi diretta del telefono

Premi `Scan phone with ADB` per leggere direttamente le app installate dal telefono, senza creare prima un CSV intermedio.

La scansione usa:

- `adb shell pm list packages` per tutti i package;
- `adb shell pm list packages -s` per identificare le system app.

Dopo la scansione premi `Run Play Store audit`.

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

Puoi caricare:

- CSV;
- TSV;
- TXT;
- output ADB `package:com.example.app`.

Sono riconosciute colonne package come:

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
