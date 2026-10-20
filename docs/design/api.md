# Contratto della API

Bozza di progettazione: nessuna di queste risorse è ancora implementata. Tutte le richieste richiedono un token Keystone nell'intestazione `X-Auth-Token`; gli orb sono visibili solo all'interno del progetto a cui appartengono.

## Risorse

| Metodo e percorso | Corpo | Risposta |
| --- | --- | --- |
| `POST /v1/orbs` | `{size, public_key, image?}` | `202` con l'orb in stato `RESERVING` |
| `GET /v1/orbs` | filtri `?status=` | `200` con l'elenco degli orb del progetto |
| `GET /v1/orbs/{id}` | — | `200` con stato, indirizzo ed eventuale errore |
| `DELETE /v1/orbs/{id}` | — | `202` con l'orb in stato `DELETING`, ripetibile senza errore |

### Creazione

```json
{
  "size": { "vcpus": 2, "memory_mb": 4096, "disk_gb": 20 },
  "public_key": "ssh-ed25519 AAAA...",
  "image": "ubuntu-24.04"
}
```

`size` finisce tale e quale nella prenotazione Blazar ([0004](../adr/0004-taglia-come-prenotazione-blazar.md)): è il requisito "ogni orb con risorse diverse" espresso dove ha effetto. Ogni valore è limitato da un massimo configurato; oltre si risponde `400`.

`public_key` è obbligatoria. Il servizio non genera coppie di chiavi e non vede mai una chiave privata: è una scelta deliberata per non avere segreti dell'utente da consegnare né da custodire.

Durante la richiesta il servizio crea il lease, poi risponde. Dopo la risposta un compito interno attende che la prenotazione diventi attiva e crea lo stack ([0005](../adr/0005-prenotazione-accanto-allo-stack.md)); Heat costruisce in modo asincrono.

### Lettura

```json
{
  "id": "0d0b...",
  "status": "ACTIVE",
  "size": { "vcpus": 2, "memory_mb": 4096, "disk_gb": 20 },
  "ssh_host": "172.24.4.17",
  "ssh_user": "ubuntu",
  "fault": null
}
```

Ogni lettura chiede lo stato a Blazar, Heat e Nova con il token del richiedente e lo riporta nella risposta: lo stato salvato è una copia, quello restituito è quello vero. `ssh_host` compare solo in stato `ACTIVE`. `fault` porta il motivo quando lo stato è `ERROR`, preso da chi l'ha prodotto (la prenotazione rifiutata, lo stack fallito) e non riscritto. La data di fine del lease non compare: non è una scadenza.

### Cancellazione

Chiede a Heat di cancellare lo stack, poi chiede a Blazar di cancellare il lease, e porta l'orb in `DELETING`. Cancellando il lease Blazar distrugge la macchina se ancora esiste e cancella il flavor della prenotazione. Su un orb già in `DELETING` o `DELETED`, o con stack o lease già spariti, risponde allo stesso modo.

## Macchina a stati

```
RESERVING ─▶ BUILDING ─▶ ACTIVE ─▶ DELETING ─▶ DELETED
    │            │          │          │          ▲
    └────────────┴──────────┴──────────┴─▶ ERROR ─┘
                                     (cancellazione esplicita)
```

| Stato | Significato | Osservazione che lo produce |
| --- | --- | --- |
| `RESERVING` | lease creato, si attende che la prenotazione diventi attiva | lease presente, prenotazione non ancora attiva |
| `BUILDING` | stack in costruzione | stack `CREATE_IN_PROGRESS` |
| `ACTIVE` | macchina raggiungibile, indirizzo disponibile | stack `CREATE_COMPLETE` e macchina `ACTIVE` |
| `ERROR` | qualcosa è fallito o è cambiato da fuori; le risorse restano in piedi per ispezione | vedi [stato conservato](stato.md#riallineamento) |
| `DELETING` | cancellazione richiesta, in corso | `DELETE` ricevuto, stack o lease ancora presenti |
| `DELETED` | stack e lease rimossi, riga conservata | stack e lease assenti dopo un `DELETE` |

`RESERVING` esiste per un motivo verificato e non per completezza: il progetto può usare il flavor della prenotazione solo quando la prenotazione è attiva, quindi lo stack non può essere creato prima.

Un orb in `ERROR` **non** si cancella da sé. È una scelta a favore della diagnosi: le risorse restano osservabili finché qualcuno non chiama `DELETE`.

## Codici di errore

| Codice | Quando |
| --- | --- |
| `400` | taglia o chiave pubblica mancanti, malformate o oltre i limiti |
| `401` | token assente, scaduto o non valido |
| `404` | orb inesistente o di un altro progetto (indistinguibili di proposito) |
| `409` | capacità esaurita: Blazar ha rifiutato la prenotazione |
| `503` | Blazar, Heat o Nova non raggiungibili |

Poiché il lease si crea durante la richiesta, la mancanza di capacità è un errore della richiesta e non lascia nessun orb. Il fallimento della costruzione, compresa la quota del progetto esaurita, si manifesta invece come `ERROR` sull'orb con il motivo riportato da Heat: lo stack viene creato dopo la risposta `202`.
