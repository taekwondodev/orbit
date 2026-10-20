# Stato conservato

Implementato in `orbit/db/api.py` e `orbit/lifecycle.py`, non ancora verificato su DevStack. Il principio che la governa: **conserviamo solo ciò di cui siamo proprietari**. Tutto il resto si chiede a chi lo possiede.

## Cosa è di altri

| Informazione | Proprietario | Come la otteniamo |
| --- | --- | --- |
| capacità concessa e stato della prenotazione | Blazar | lease |
| flavor della taglia | Blazar | identificativo della prenotazione |
| esistenza ed esito delle risorse | Heat | stato dello stack |
| indirizzo SSH | Heat | output dello stack |
| esistenza e stato della macchina | Nova | la macchina indicata dall'output dello stack |
| identità e ruoli del consumatore | Keystone | token della richiesta |

## La tabella `orbs`

```
id                  uuid        chiave primaria, è l'identificativo pubblico dell'orb
project_id          string      progetto del consumatore, filtro di ogni lettura
user_id             string      chi ha chiesto l'orb
vcpus               int         la taglia chiesta
memory_mb           int
disk_gb             int
image               string      l'immagine chiesta, da cui dipende l'utente SSH
lease_id            uuid        il lease Blazar
reservation_id      uuid        la prenotazione dentro quel lease, usata come flavor
stack_id            uuid        lo stack Heat, vuoto finché non è creato
status              enum        vedi la macchina a stati nel contratto della API
fault               text        motivo dell'errore, copiato da chi l'ha prodotto
created_at          timestamp
updated_at          timestamp
deleted_at          timestamp   conservata per lo storico
```

La tabella esiste perché il servizio possiede tre cose che nessun altro conserva: il legame fra un orb, il suo lease e il suo stack; la taglia e l'immagine chieste, che sopravvivono al lease; la storia degli orb cancellati. Due colonne sono copie dichiarate:

- `status` è una copia dell'ultima osservazione. Ogni lettura la ricalcola da Blazar, Heat e Nova e la riscrive; serve a filtrare l'elenco.
- `fault` è una copia del motivo di un fallimento altrui, conservata perché lo stack in errore potrebbe essere cancellato prima che qualcuno legga l'orb.

Nessun segreto è conservato: il servizio non tiene né token né deleghe ([0002](../adr/0002-risorse-nel-progetto-dell-utente.md)).

## Riallineamento

Ogni lettura di un orb, singola o in elenco, confronta ciò che la tabella afferma con ciò che Blazar, Heat e Nova mostrano col token del richiedente, e corregge la tabella. Non il contrario: se la realtà e la tabella divergono, ha ragione la realtà.

| Osservazione | Stato risultante |
| --- | --- |
| lease in attesa di attivazione | `RESERVING` |
| nessuno stack, orb creato da meno del limite di attesa | `RESERVING` |
| nessuno stack, orb creato da più del limite di attesa | `ERROR`, "creazione interrotta" |
| lease in errore | `ERROR`, motivo dal lease |
| stack `CREATE_IN_PROGRESS` | `BUILDING` |
| stack `CREATE_COMPLETE`, macchina `ACTIVE` | `ACTIVE` |
| stack `CREATE_FAILED` | `ERROR`, motivo dallo stack |
| stack `CREATE_COMPLETE`, macchina assente o non `ACTIVE` | `ERROR`, "macchina non più disponibile" |
| lease assente, orb non in `DELETING` | `ERROR`, "prenotazione non più presente" |
| stack assente dopo essere stato creato, orb non in `DELETING` | `ERROR`, "stack non più presente" |
| orb in `DELETING`, stack o lease ancora presenti | `DELETING` |
| orb in `DELETING`, stack e lease assenti | `DELETED` |
| stack `DELETE_FAILED` | `ERROR`, motivo dallo stack; un nuovo `DELETE` ritenta |

Un orb già in `ERROR` che resta in errore conserva il primo motivo, che è quello utile alla diagnosi; se invece la realtà torna a posto, per esempio una macchina spenta viene riaccesa, l'orb torna `ACTIVE`. Durante la cancellazione lo stack si cerca per nome anche se l'orb non ne ha registrato uno: il compito di creazione potrebbe averlo creato senza aver fatto in tempo a scriverlo.

La macchina va letta oltre allo stack perché Heat non si accorge di una macchina cancellata o spenta da fuori: lo stack resta `CREATE_COMPLETE`. Il lease va letto perché, se qualcuno lo cancella a mano, Blazar distrugge la macchina.

Il compito che attende la prenotazione e crea lo stack vive solo in memoria, nel processo che ha ricevuto la richiesta: nessun altro processo può sapere se è ancora in corso. Per questo il criterio è il tempo: un orb senza stack oltre il limite di attesa configurato si considera interrotto, e il compito stesso rinuncia allo scadere dello stesso limite.

Ogni azione è ripetibile senza danno: cancellare uno stack o un lease già cancellati e rileggere risorse sparite devono portare allo stesso risultato.

## Nomi deterministici

Lease e stack di un orb si chiamano entrambi `orbit-<orb_id>`, e lo stack porta l'etichetta `orbit`. I nomi permettono di ritrovare le risorse di un orb anche se la scrittura in tabella non è andata a buon fine, e rendono un secondo tentativo riconoscibile invece di produrre un duplicato; l'etichetta permette di leggere tutti gli stack degli orb di un progetto con una sola chiamata a Heat.
