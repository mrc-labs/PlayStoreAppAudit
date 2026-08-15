# Play Store App Audit

Windows utility per controllare in blocco i package Android e ottenere direttamente nell'app:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- età dell'ultimo aggiornamento in giorni;
- stato del listing;
- titolo attuale sullo Store;
- fonte della data di aggiornamento;
- classificazione visuale della criticità;
- identificazione delle system app quando possibile.

## GUI Qt 6 / PySide6

La GUI principale è ora `playstore_audit_qt.py`, costruita con PySide6 / Qt 6.

Vantaggi principali rispetto alla precedente GUI Tkinter:

- supporto HiDPI nativo e scaling per-monitor;
- layout e controlli più moderni;
- `QTableView` con sorting nativo;
- colonne trascinabili e riordinabili;
- filtri istantanei tramite proxy model;
- migliore resa grafica dei colori di criticità;
- operazioni ADB/audit eseguite senza bloccare l'interfaccia principale.

I vecchi file Tkinter sono temporaneamente mantenuti nel repository come fallback durante la migrazione, ma GitHub Actions e gli script Windows costruiscono/avviano la versione Qt 6.

## Impostazioni principali

- `Country`: determina il mercato Google Play controllato e può cambiare la disponibilità del listing. Su Windows viene inizializzato automaticamente dalla Region configurata nel sistema operativo (es. Switzerland -> `ch`, Italy -> `it`), ma resta modificabile.
- `Parallel threads`: controlla il parallelismo dell'audit.

`Language` è dentro `Advanced` come `Store language`, con default `en`. Serve soprattutto per titoli/testi localizzati e non determina il mercato controllato.

## Advanced

La sezione `Advanced` è chiusa di default e contiene:

- `Store language`, default `en`;
- `Skip system apps during audit`, disattivato di default.

Se `Skip system apps during audit` è attivo, le system app classificate vengono escluse prima delle richieste al Play Store. L'audit è più rapido, ma quelle app non vengono analizzate e non possono comparire nei risultati.

## Tabella risultati

La tabella permette di:

- ordinare i risultati cliccando sulle intestazioni;
- trascinare le intestazioni per riordinare le colonne;
- ordinare numericamente `Age (days)`;
- filtrare rapidamente con il campo `Filter apps`;
- cliccare i contatori colorati per mostrare una sola classe di criticità;
- nascondere o mostrare le system app senza rieseguire l'audit;
- fare doppio clic su una riga per aprire il listing Play Store;
- esportare il CSV soltanto quando serve.

### Hide system apps

`Hide system apps` è un filtro puramente visuale. Quando le system app sono state analizzate, puoi nasconderle o mostrarle istantaneamente senza rilanciare l'audit.

La classificazione system app usa, in ordine:

1. eventuale colonna CSV come `is_system`, `system`, `system_app` o `app_type`;
2. ADB, se è collegato e autorizzato un telefono Android;
3. un fallback prudente basato sui package chiaramente di sistema.

Con una scansione diretta del telefono via ADB la classificazione system/user è esatta per quel dispositivo.

## Criticità e colori

Gli sfondi sono volutamente molto tenui.

- `Removed`: app non più trovata sul Play Store;
- `Stale`: ultimo aggiornamento più vecchio di 730 giorni;
- `Aging`: ultimo aggiornamento più vecchio di 365 giorni e non oltre 730 giorni;
- `Store anomaly`: listing trovato soltanto nel locale fallback o altra anomalia esplicita di disponibilità;
- `Other`: data assente/non interpretabile, errore di richiesta o altra situazione non determinabile con sicurezza;
- `Current`: ultimo aggiornamento non più vecchio di 365 giorni.

La colonna `Criticality` è ordinabile per severità. I contatori colorati sono cliccabili e `All` ripristina la vista completa.

## Analisi diretta del telefono e ADB

Premi `Scan phone with ADB` per leggere direttamente le app installate dal telefono.

L'app cerca automaticamente ADB in:

- PATH di Windows;
- cartella dell'app / `platform-tools`;
- Android Studio SDK (`%LOCALAPPDATA%\Android\Sdk\platform-tools`);
- `ANDROID_SDK_ROOT` e `ANDROID_HOME`;
- copia gestita dall'app in `%LOCALAPPDATA%\PlayStoreAppAudit\platform-tools`.

Se ADB non è installato, l'app propone di scaricare direttamente da Google l'ultima versione Windows di Android SDK Platform-Tools e installarla nella cartella utente dell'app. I binari Google non sono inclusi nell'EXE.

Se il telefono è `unauthorized`, sbloccalo e accetta `Allow USB debugging?`. Se non compare, controlla cavo dati, modalità USB e driver OEM Windows.

La scansione usa:

- `adb shell pm list packages` per tutti i package;
- `adb shell pm list packages -s` per identificare le system app.

## Creare l'EXE Windows online

`.github/workflows/build-windows-exe.yml` usa un runner Windows GitHub Actions e genera `PlayStoreAppAudit.exe` dalla GUI Qt 6 `playstore_audit_qt.py`.

L'artifact della build si chiama `PlayStoreAppAudit-Windows-Qt6`.

## Altri metodi

- Python su Windows: `run_windows_gui.bat`
- Build locale Windows: `build_windows_exe.bat`
- CLI: `playstore_audit_cli.py`

## Input file supportati

Puoi caricare CSV, TSV, TXT oppure output ADB `package:com.example.app`.

Sono riconosciute colonne package come `package_name`, `package`, `packageName`, `packageId`, `app_id` e `id`. Il nome dell'app è opzionale.
