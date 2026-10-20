# Contratto della API

Bozza di progettazione: nessuna di queste risorse è ancora implementata. Tutte le richieste richiedono un token Keystone nell'intestazione `X-Auth-Token`; le sessioni sono visibili solo all'interno del progetto a cui appartengono.

## Risorse

| Metodo e percorso | Corpo | Risposta |
| --- | --- | --- |
| `POST /v1/sessions` | `{size, public_key, image?, ttl_seconds?}` | `202` con la sessione in stato `PENDING` |
| `GET /v1/sessions` | filtri `?status=` | `200` con l'elenco delle sessioni del progetto |
| `GET /v1/sessions/{id}` | — | `200` con stato, indirizzo, scadenza ed eventuale errore |
| `POST /v1/sessions/{id}/renew` | `{ttl_seconds}` | `200` con la nuova scadenza |
| `DELETE /v1/sessions/{id}` | — | `204`, ripetibile senza errore |

### Creazione

```json
{
  "size": { "vcpus": 2, "memory_mb": 4096, "disk_gb": 20 },
  "public_key": "ssh-ed25519 AAAA...",
  "image": "ubuntu-24.04",
  "ttl_seconds": 7200
}
```

`size` finisce tale e quale nella prenotazione Blazar: è il requisito "ogni sessione con risorse diverse" espresso dove ha effetto.

`public_key` è obbligatoria. Il servizio non genera coppie di chiavi e non vede mai una chiave privata: è una scelta deliberata per non avere segreti dell'utente da consegnare né da custodire.

### Lettura

```json
{
  "id": "0d0b...",
  "status": "ACTIVE",
  "size": { "vcpus": 2, "memory_mb": 4096, "disk_gb": 20 },
  "ssh_host": "172.24.4.17",
  "ssh_user": "ubuntu",
  "expires_at": "2026-10-20T18:30:00Z",
  "fault": null
}
```

`ssh_host` compare solo in stato `ACTIVE`. `fault` porta il motivo quando lo stato è `ERROR`, preso da chi l'ha prodotto (lo stack fallito o la prenotazione rifiutata) e non riscritto.

### Rinnovo

Sposta in avanti la data di fine del lease. Fallisce con `409` se la sessione non è viva, con `403` se il prolungamento eccede il limite configurato. Non tocca lo stack.

## Macchina a stati

```
PENDING ─▶ RESERVING ─▶ BUILDING ─▶ ACTIVE ─▶ DELETING ─▶ DELETED
   │           │            │          │          ▲
   └───────────┴────────────┴──────────┴──▶ ERROR ┘
                                            (cancellazione esplicita)
```

| Stato | Significato | Chi lo fa cambiare |
| --- | --- | --- |
| `PENDING` | richiesta accettata, nulla creato | api |
| `RESERVING` | lease creato, si attende che la prenotazione diventi attiva | engine |
| `BUILDING` | stack in creazione | engine |
| `ACTIVE` | macchina raggiungibile, indirizzo disponibile | engine |
| `ERROR` | qualcosa è fallito; le risorse restano in piedi per ispezione | engine o cleaner |
| `DELETING` | cancellazione in corso | engine |
| `DELETED` | risorse rimosse, riga conservata | engine |

`RESERVING` esiste per un motivo verificato e non per completezza: il flavor che rappresenta la prenotazione compare solo quando la prenotazione diventa attiva, quindi lo stack non può essere creato prima.

Una sessione in `ERROR` **non** si cancella da sé. È una scelta a favore della diagnosi: le risorse restano osservabili finché qualcuno non chiama `DELETE`. Chi preferisse l'opposto dovrebbe aspettarsi di non poter mai capire perché una sessione è fallita.

## Codici di errore

| Codice | Quando |
| --- | --- |
| `400` | taglia o chiave pubblica mancanti o malformate |
| `401` | token assente, scaduto o non valido |
| `403` | delega rifiutata dall'utente, oppure limite di rinnovo superato |
| `404` | sessione inesistente o di un altro progetto (indistinguibili di proposito) |
| `409` | operazione incompatibile con lo stato corrente |
| `503` | Blazar o Heat non raggiungibili |

L'esaurimento della capacità prenotabile si manifesta come `ERROR` sulla sessione con il motivo riportato da Blazar, non come errore della richiesta: la prenotazione viene valutata dopo la risposta `202`.
