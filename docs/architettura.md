# Architettura

Chi fa cosa, dove passa il confine di proprietà e in che ordine avvengono le cose. Le scelte che hanno prodotto questa forma sono registrate in [docs/adr](adr/); qui si descrive il risultato.

## Componenti

| Componente | Responsabilità | Non fa |
| --- | --- | --- |
| `agentsession-api` | riceve le richieste HTTP, autentica il token, valida, scrive la sessione in stato iniziale e risponde subito | non chiama Heat né Blazar |
| `agentsession-engine` | esegue la sequenza lenta: trust, prenotazione, attesa, stack; aggiorna lo stato della sessione | non riceve richieste HTTP |
| `agentsession-cleaner` | compito periodico: cancella gli stack delle sessioni il cui lease è finito, e riallinea lo stato quando la realtà è cambiata da fuori | non decide quando una sessione scade |
| tabella `sessions` | il legame fra sessione, lease e stack, il trust ID cifrato e lo stato | non è la verità sulle risorse |

La separazione fra API e motore esiste per una ragione concreta, non per simmetria con gli altri servizi OpenStack: fra la creazione del lease e la disponibilità del flavor della prenotazione c'è un'attesa, e una richiesta HTTP non può restare appesa per tutto quel tempo. La API risponde `202` e il motore continua.

## Confine di proprietà

```
                     ┌──────────────── agentsession ────────────────┐
  client  ──HTTP──▶  │  api  ──coda──▶  engine        cleaner       │
                     │        tabella: sessione, lease, stack, trust│
                     └───────┬──────────────┬──────────────┬────────┘
                             │              │              │
                        Keystone         Blazar           Heat
                      (chi sei,        (quanta         (quali risorse,
                       e la delega)     capacità        create e distrutte
                                        e fino a        in ordine)
                                        quando)              │
                                                         Nova, Neutron
```

Regole che non vanno violate perché sono il senso del progetto:

- **Il servizio non crea risorse.** Non chiama Nova né Neutron. Se un giorno serve una risorsa in più nella sandbox, si aggiunge al template.
- **Il servizio non decide la scadenza.** La verità sull'ora di fine è il lease: la colonna `expires_at` è una copia di comodo, da rileggere e non da credere.
- **Il servizio non entra nella sandbox.** Non esegue comandi, non copia file, non sa cosa ci gira. Consegna un indirizzo e un utente SSH.

## Sequenza di una sessione

```
client            api           engine          Keystone   Blazar        Heat
  │  POST /sessions │              │                │         │            │
  ├────────────────▶│              │                │         │            │
  │                 ├─ trust ──────┼───────────────▶│         │            │
  │                 │◀─ trust ID ──┼────────────────┤         │            │
  │   202 BUILDING  │              │                │         │            │
  │◀────────────────┤─── compito ─▶│                │         │            │
  │                 │              ├─ lease (taglia, fine) ──▶│            │
  │                 │              │◀─ reservation_id ────────┤            │
  │                 │              ├─ attesa: prenotazione attiva ─────────┤
  │                 │              ├─ stack(flavor=reservation_id) ───────▶│
  │                 │              │◀─ indirizzo SSH ──────────────────────┤
  │  GET /sessions/{id} → ACTIVE   │                │         │            │
  │                 │              │                │         │            │
  │  POST /{id}/renew              ├─ nuova data di fine ────▶│            │
  │                 │              │                │         │            │
  │                 │   scadenza   │                ├─ termina la macchina │
  │                 │   cleaner ──▶│─ token dal trust ──────▶ cancella ───▶│
```

Il passaggio che richiede attenzione è l'ultimo: Blazar termina la macchina prenotata, non lo stack. Senza il pulitore, resterebbe uno stack con dentro una macchina inesistente, e con esso chiave, firewall e indirizzo. È il debito che l'adozione di Blazar introduce, ed è il motivo per cui il pulitore non è un dettaglio implementativo ma un componente dichiarato.

## Installazione

Il servizio si installa come plugin DevStack: un repository con una cartella `devstack/` contenente `settings` (che dichiara il plugin e abilita i servizi) e `plugin.sh`, chiamato nelle fasi `pre-install`, `install`, `post-config` ed `extra` di `stack.sh`, più `unstack` e `clean`.

Oltre ai propri processi, il plugin deve:

- dichiarare la dipendenza dai plugin di Heat e Blazar, che vanno abilitati prima nel `local.conf`;
- registrare servizio ed endpoint nel catalogo di Keystone;
- registrare l'host di calcolo in Blazar, senza il quale nessun lease è creabile.
