# Stato conservato

Bozza di progettazione. Il principio che la governa: **conserviamo solo ciò di cui siamo proprietari**. Tutto il resto si chiede a chi lo possiede.

## Cosa è di altri

| Informazione | Proprietario | Come la otteniamo |
| --- | --- | --- |
| esistenza ed esito delle risorse | Heat | stato dello stack |
| indirizzo SSH | Heat | output dello stack |
| esistenza e stato della macchina | Nova | la macchina indicata dall'output dello stack |
| identità e ruoli del consumatore | Keystone | token della richiesta |
| quota disponibile | Nova e Neutron | esito della creazione dello stack |

## La tabella `orbs`

```
id                  uuid        chiave primaria, è l'identificativo pubblico dell'orb
project_id          string      progetto del consumatore, filtro di ogni lettura
user_id             string      chi ha chiesto l'orb
vcpus               int         la taglia chiesta
memory_mb           int
disk_gb             int
flavor_id           string      il flavor privato dell'orb
stack_id            uuid        lo stack Heat
status              enum        vedi la macchina a stati nel contratto della API
fault               text        motivo dell'errore, copiato da chi l'ha prodotto
created_at          timestamp
updated_at          timestamp
deleted_at          timestamp   conservata per lo storico
```

La tabella esiste perché il servizio possiede tre cose che nessun altro conserva: il legame fra un orb, il suo flavor e il suo stack; la taglia chiesta, che sopravvive al flavor; la storia degli orb cancellati. Due colonne sono copie dichiarate:

- `status` è una copia dell'ultima osservazione. Ogni lettura la ricalcola da Heat e Nova e la riscrive; serve a filtrare l'elenco e al pulitore, che non ha il token dell'utente e non può leggere lo stack.
- `fault` è una copia del motivo di un fallimento altrui, conservata perché lo stack in errore potrebbe essere cancellato prima che qualcuno legga l'orb.

Nessun segreto è conservato: il servizio non tiene né token né deleghe ([0002](../adr/0002-risorse-nel-progetto-dell-utente.md)).

## Riallineamento

Ogni lettura di un orb, singola o in elenco, confronta ciò che la tabella afferma con ciò che Heat e Nova mostrano col token del richiedente, e corregge la tabella. Non il contrario: se la realtà e la tabella divergono, ha ragione la realtà.

| Osservazione | Stato risultante |
| --- | --- |
| stack `CREATE_IN_PROGRESS` | `BUILDING` |
| stack `CREATE_COMPLETE`, macchina `ACTIVE` | `ACTIVE` |
| stack `CREATE_FAILED` | `ERROR`, motivo dallo stack |
| stack `CREATE_COMPLETE`, macchina assente o non `ACTIVE` | `ERROR`, "macchina non più disponibile" |
| stack assente, orb non in `DELETING` | `ERROR`, "stack non più presente" |
| stack `DELETE_IN_PROGRESS` | `DELETING` |
| stack `DELETE_COMPLETE` o assente, orb in `DELETING` | `DELETED` |
| stack `DELETE_FAILED` | `ERROR`, motivo dallo stack; un nuovo `DELETE` ritenta |

La macchina va letta oltre allo stack perché Heat non si accorge di una macchina cancellata o spenta da fuori: lo stack resta `CREATE_COMPLETE`.

## Pulitore

Il pulitore è un compito periodico che usa solo la credenziale del servizio e tocca solo i flavor degli orb. Un flavor `orbit-<orb_id>` viene cancellato quando:

- l'orb è in `DELETING` o `DELETED`, oppure non ha una riga in tabella ed è più vecchio di un intervallo configurato (creazione interrotta a metà);
- e nessuna macchina, in nessun progetto, usa quel flavor.

La seconda condizione è quella che conta: un flavor non si cancella mentre la macchina che lo usa esiste ([0004](../adr/0004-flavor-privato-per-ogni-orb.md)). Il pulitore non cambia lo stato degli orb: non può vedere gli stack, e un orb resta in `DELETING` finché una lettura non osserva lo stack sparito.

Ogni azione è ripetibile senza danno: cancellare un flavor già cancellato e rileggere uno stack sparito devono portare allo stesso risultato. Il pulitore verrà interrotto a metà, e la ripresa deve essere indistinguibile da una prima esecuzione.

## Nomi deterministici

Flavor e stack di un orb si chiamano entrambi `orbit-<orb_id>`, e lo stack porta l'etichetta `orbit`. I nomi permettono di ritrovare le risorse di un orb anche se la scrittura in tabella non è andata a buon fine, e rendono un secondo tentativo riconoscibile invece di produrre un duplicato; l'etichetta permette di leggere tutti gli stack degli orb di un progetto con una sola chiamata a Heat.
