# Play Store App Audit

Utility per controllare in blocco i package Android e ottenere direttamente nell'app:

- ultima data di aggiornamento pubblicata sul Google Play Store;
- età dell'ultimo aggiornamento in giorni;
- stato del listing;
- titolo attuale sullo Store;
- fonte della data di aggiornamento;
- classificazione visuale della criticità;
- identificazione delle system app quando possibile.

## Impostazioni principali

La schermata principale mantiene soltanto i parametri realmente utili nell'uso normale:

- `Country`: determina il mercato Google Play controllato e può cambiare la disponibilità del listing. Su Windows viene inizializzato automaticamente dalla Region configurata nel sistema operativo (es. Switzerland -> `ch`, Italy -> `it`), ma resta modificabile;
- `Parallel threads`: controlla il parallelismo dell'audit.

`Language` non è mostrato nella schermata principale. È disponibile dentro `Advanced` come `Store language`, con default `en`, e serve soprattutto per titoli/testi localizzati; non determina il mercato controllato.

## Advanced

La sezione `Advanced` è chiusa di default e contiene:

- `Store language`, default `en`;
- `Skip system apps during audit`, disattivato di default.

Se `Skip system apps during audit` è attivo, le system app classificate vengono escluse prima delle richieste al Play Store. L'audit è più rapido, ma quelle app non vengono analizzate e non possono comparire nei risultati.

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

Il checkbox `Hide system apps` è un filtro puramente visuale. Quando le system app sono state analizzate, puoi nasconderle o mostrarle istantaneamente senza rilanciare l'audit.

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

La colonna `Criticality` è ordinabile per severità. I contatori colorati sopra la tabella sono cliccabili: clicca un colore per filtrare quella classe, cliccalo di nuovo oppure premi `All` per tornare alla vista completa.

## Analisi diretta del telefono e ADB

Premi `Scan phone with ADB` per leggere direttamente le app installate dal telefono.

L'app cerca automaticamente ADB in:

- PATH di Windows;
- cartella dell'app / `platform-tools`;
- Android Studio SDK (`%LOCALAPPDATA%\Android\Sdk\platform-tools`);
- `ANDROID_SDK_ROOT` e `ANDROID_HOME`;
- copia gestita dall'app in `%LOCALAPPDATA%\PlayStoreAppAudit\platform-tools`.

Se ADB non è installato, l'app propone di scaricare direttamente da Google l'ultima versione Windows di Android SDK Platform-Tools e installarla nella cartella utente dell'app. Il download avviene a runtime dal server Google, dopo conferma dell'utente; i binari Google non sono inclusi nell'EXE.

Se il telefono viene visto come `unauthorized`, l'app indica di sbloccare il telefono e accettare il prompt RSA `Allow USB debugging?`. Se ADB è installato ma il telefono non compare, controlla cavo dati, modalità USB e driver OEM Windows.

La scansione usa:

- `adb shell pm list packages` per tutti i package;
- `adb shell pm list packages -s` per identificare le system app.

Dopo la scansione premi `Run Play Store audit`.

## Creare l'EXE Windows online

Il repository contiene `.github/workflows/build-windows-exe.yml`.

Il workflow GitHub Actions gira su un runner Windows e genera `PlayStoreAppAudit.exe` come artifact. La build Windows usa `playstore_audit_windows.py`, che aggiunge rilevamento automatico della Region e gestione ADB alla GUI principale.

## Altri metodi

- Google Colab: `playstore_audit_final_colab.ipynb`
- Python su Windows: `run_windows_gui.bat`
- Build locale Windows: `build_windows_exe.bat`

## Input file supportati

Puoi caricare CSV, TSV, TXT oppure output ADB `package:com.example.app`.

Sono riconosciute colonne package come `package_name`, `package`, `packageName`, `packageId`, `app_id` e `id`. Il nome dell'app è opzionale.
