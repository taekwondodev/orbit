# Stato conservato

Bozza di progettazione. Il principio che la governa: **conserviamo solo ciò di cui siamo proprietari**. Tutto il resto si chiede a chi lo possiede.

## Cosa è di altri

| Informazione | Proprietario | Come la otteniamo |
| --- | --- | --- |
| esistenza ed esito delle risorse | Heat | stato dello stack |
| indirizzo SSH | Heat | output dello stack |
| ora di fine e stato della prenotazione | Blazar | lease |
| identità e ruoli del consumatore | Keystone | token della richiesta |
| capacità disponibile | Blazar | esito della creazione del lease |

## La tabella `sessions`

```
id                  uuid        chiave primaria, è l'identificativo pubblico della sessione
project_id          string      progetto del consumatore, filtro di ogni lettura
user_id             string      chi ha chiesto la sessione
lease_id            uuid        il lease Blazar
reservation_id      uuid        la prenotazione dentro quel lease, usata come flavor
stack_id            uuid        lo stack Heat
trust_id            bytes       cifrato: la delega con cui agire quando l'utente non c'è
status              enum        vedi la macchina a stati nel contratto della API
fault               text        motivo dell'errore, copiato da chi l'ha prodotto
expires_at          timestamp   copia di comodo della fine del lease, non autorevole
created_at          timestamp
updated_at          timestamp
deleted_at          timestamp   conservata per lo storico
```

Dieci colonne, nessuna delle quali duplica un dato che qualcun altro possiede meglio, con due eccezioni dichiarate:

- `expires_at` è una copia. Serve perché il pulitore deve poter selezionare le sessioni candidate senza interrogare Blazar per ognuna. La verità resta il lease: prima di cancellare, il pulitore rilegge.
- `fault` è una copia del motivo di un fallimento altrui, conservata perché lo stack in errore potrebbe essere cancellato prima che qualcuno legga la sessione.

`trust_id` è l'unica ragione per cui questa tabella esiste in forma cifrata: è un segreto che permette di agire al posto dell'utente, e non può stare in un'etichetta di uno stack o in un campo leggibile. La chiave di cifratura vive nella configurazione del servizio, come Heat fa con il proprio trust ID.

## Riallineamento

Un compito periodico confronta ciò che la tabella afferma con ciò che Blazar e Heat mostrano, e corregge la tabella. Non il contrario: se la realtà e la tabella divergono, ha ragione la realtà.

| Osservazione | Azione |
| --- | --- |
| lease finito, stack ancora presente | cancella lo stack con la delega, poi `DELETED` |
| stack sparito, sessione `ACTIVE` | `ERROR` con il motivo "stack non più presente" |
| lease sparito, stack presente | cancella lo stack, poi `ERROR` |
| sessione `DELETING` da troppo tempo | ritenta la cancellazione, poi `ERROR` |

Ogni azione è ripetibile senza danno: cancellare uno stack già cancellato, rileggere un lease finito e riscrivere lo stesso stato devono portare allo stesso risultato. Il pulitore verrà interrotto a metà, e la ripresa deve essere indistinguibile da una prima esecuzione.

## Nomi deterministici

Lease e stack di una sessione si chiamano entrambi `agentsess-<session_id>`. Non è un vezzo: permette di ritrovare le risorse orfane di una sessione anche se la scrittura in tabella non è andata a buon fine, e rende un secondo tentativo riconoscibile invece di produrre un duplicato.
