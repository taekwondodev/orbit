# Contratto della API

Bozza di progettazione: nessuna di queste risorse è ancora implementata. Tutte le richieste richiedono un token Keystone nell'intestazione `X-Auth-Token`; gli orb sono visibili solo all'interno del progetto a cui appartengono.

## Risorse

| Metodo e percorso | Corpo | Risposta |
| --- | --- | --- |
| `POST /v1/orbs` | `{size, public_key, image?}` | `202` con l'orb in stato `BUILDING` |
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

`size` diventa tale e quale il flavor privato dell'orb ([0004](../adr/0004-flavor-privato-per-ogni-orb.md)): è il requisito "ogni orb con risorse diverse" espresso dove ha effetto. Ogni valore è limitato da un massimo configurato; oltre si risponde `400`.

`public_key` è obbligatoria. Il servizio non genera coppie di chiavi e non vede mai una chiave privata: è una scelta deliberata per non avere segreti dell'utente da consegnare né da custodire.

Durante la richiesta il servizio crea il flavor, ne concede l'accesso al progetto e chiede a Heat lo stack. Heat costruisce in modo asincrono, quindi la risposta arriva prima che la macchina esista.

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

Ogni lettura chiede lo stato a Heat con il token del richiedente e lo riporta nella risposta: lo stato salvato è una copia, quello restituito è quello vero. `ssh_host` compare solo in stato `ACTIVE`. `fault` porta il motivo quando lo stato è `ERROR`, preso da chi l'ha prodotto (lo stack fallito, il rifiuto di Nova) e non riscritto.

### Cancellazione

Chiede a Heat di cancellare lo stack e porta l'orb in `DELETING`. Su un orb già in `DELETING` o `DELETED`, o con lo stack già sparito, risponde allo stesso modo. Il flavor non viene cancellato qui: lo rimuove il pulitore quando nessuna macchina lo usa più.

## Macchina a stati

```
BUILDING ─▶ ACTIVE ─▶ DELETING ─▶ DELETED
    │          │          │          ▲
    └──────────┴──────────┴─▶ ERROR ─┘
                          (cancellazione esplicita)
```

| Stato | Significato | Osservazione che lo produce |
| --- | --- | --- |
| `BUILDING` | flavor creato, stack in costruzione | stack `CREATE_IN_PROGRESS` |
| `ACTIVE` | macchina raggiungibile, indirizzo disponibile | stack `CREATE_COMPLETE` e macchina `ACTIVE` |
| `ERROR` | qualcosa è fallito o è cambiato da fuori; le risorse restano in piedi per ispezione | vedi [stato conservato](stato.md#riallineamento) |
| `DELETING` | cancellazione richiesta, in corso | `DELETE` ricevuto, stack `DELETE_IN_PROGRESS` |
| `DELETED` | stack rimosso, riga conservata | stack `DELETE_COMPLETE` o assente dopo un `DELETE` |

Un orb in `ERROR` **non** si cancella da sé. È una scelta a favore della diagnosi: le risorse restano osservabili finché qualcuno non chiama `DELETE`.

## Codici di errore

| Codice | Quando |
| --- | --- |
| `400` | taglia o chiave pubblica mancanti, malformate o oltre i limiti |
| `401` | token assente, scaduto o non valido |
| `404` | orb inesistente o di un altro progetto (indistinguibili di proposito) |
| `503` | Nova o Heat non raggiungibili |

Il fallimento della costruzione, compresa la quota del progetto esaurita, si manifesta come `ERROR` sull'orb con il motivo riportato da Heat, non come errore della richiesta: la macchina viene creata dopo la risposta `202`.
