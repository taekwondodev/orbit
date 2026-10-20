# agentsession

Servizio OpenStack che assegna a un consumatore una **sandbox effimera**: una macchina virtuale isolata, con risorse scelte al momento della richiesta e una durata a scadenza, raggiungibile in SSH e riconsegnata automaticamente quando il tempo finisce.

Nasce come progetto universitario su DevStack. Il caso d'uso che lo motiva è l'isolamento delle sessioni di un agente di sviluppo: oggi ogni sessione ottiene una copia del repository sul disco locale, qui ottiene una macchina intera. Il servizio non sa nulla dell'agente: espone una sessione, non un ambiente di lavoro.

## Stato

Fase di progettazione. Nessun codice eseguito e nessun componente installato: tutte le affermazioni tecniche in questi documenti sono tratte dalla documentazione ufficiale o dal codice sorgente di OpenStack, con il collegamento alla fonte accanto. Dove un fatto non è ancora stato osservato, è dichiarato come da verificare.

## Com'è fatta una sessione

```
POST /v1/sessions                     il client chiede una sandbox per due ore
  │
  ├─ Keystone    l'utente delega i suoi ruoli al servizio (trust), il servizio conserva il trust ID
  ├─ Blazar      prenotazione con processori, memoria, disco e ora di fine
  ├─ Heat        stack con chiave, firewall, porta, IP e macchina dentro la prenotazione
  └─ risposta    indirizzo e utente SSH
                                      alla scadenza Blazar termina la macchina,
                                      il servizio usa la delega e cancella lo stack
```

Il servizio possiede il concetto di sessione e la sua anagrafica. Non possiede le risorse: quelle appartengono al progetto dell'utente, le crea Heat e il loro tempo di vita lo governa Blazar.

## Documenti

| Documento | Contenuto |
| --- | --- |
| [CONTEXT](CONTEXT.md) | glossario: cosa significano sessione, sandbox, lease, prenotazione, stack, trust |
| [Architettura](docs/architettura.md) | componenti, confini di proprietà, sequenza completa di una sessione |
| [Contratto della API](docs/design/api.md) | risorse HTTP, codici di stato, macchina a stati |
| [Stato conservato](docs/design/stato.md) | la tabella del servizio e cosa invece è di altri |
| [Template della sandbox](templates/sandbox.yaml) | la descrizione Heat delle risorse di una sessione |
| [Decisioni](docs/adr/) | le scelte di forma, con motivazione, alternative scartate e fonti |

## Decisioni già prese

| # | Decisione |
| --- | --- |
| [0001](docs/adr/0001-provisioning-delegato-a-heat.md) | Le risorse della sandbox le crea Heat da un template, non il codice del servizio |
| [0002](docs/adr/0002-risorse-nel-progetto-dell-utente.md) | Le risorse nascono nel progetto di chi chiede la sessione e consumano la sua quota |
| [0003](docs/adr/0003-delega-con-trust-di-keystone.md) | Le operazioni differite usano una trust di Keystone, non una credenziale amministrativa |
| [0004](docs/adr/0004-scadenza-governata-da-blazar.md) | La durata della sessione è una prenotazione Blazar, non un timer del servizio |
| [0005](docs/adr/0005-prenotazione-accanto-allo-stack.md) | La prenotazione si crea prima dello stack e fuori da esso, per poterla prolungare |
