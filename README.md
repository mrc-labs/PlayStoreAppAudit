# Play Store App Audit

Utility per controllare in blocco i package Android e ottenere direttamente nell'app:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- età dell'ultimo aggiornamento in giorni;
- stato del listing;
- titolo attuale sullo Store;
- fonte della data di aggiornamento;
- classificazione visuale della criticità;
- identificazione delle system app quando possibile.

## Tabella risultati

La versione Windows mostra i risultati direttamente in una tabella interna.

La tabella permette di:

- ordinare i risultati cliccando sulle intestazioni delle colonne;
- ordinare numericamente anche `Age (days)`;
- filtrare rapidamente le righe con il campo `Filter`;
- cliccare i contatori colorati per mostrare una sola classe di criticità;
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

I colori di sfondo sono volutamente molto tenui per mantenere leggibile la tabella.

- 🔴 `Removed`: app non più trovata sul Play Store;
- 🟠 `Stale`: ultimo aggiornamento più vecchio di 730 giorni;
- 🟡 `Aging`: ultimo aggiornamento più vecchio di 365 giorni e non oltre 730 giorni;
- 🔵 `Store anomaly`: listing trovato soltanto nel locale fallback o altra anomalia esplicita di disponibilità sullo Store;
- 🟣 `Other`: data assente/non interpretabile, errore di richiesta o altra situazione non determinabile con sicurezza;
- 🟢 `Current`: ultimo aggiornamento non più vecchio di 365 giorni.

La colonna `Criticality` è ordinabile per severità.

I contatori colorati sopra la tabella sono cliccabili: clicca un colore per filtrare quella classe, cliccalo di nuovo oppure premi `All` per tornare alla vista completa.

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
