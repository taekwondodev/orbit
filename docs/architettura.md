# Architettura

Chi fa cosa, dove passa il confine di proprietà e in che ordine avvengono le cose. Le scelte che hanno prodotto questa forma sono registrate in [docs/adr](adr/); qui si descrive il risultato.

## Componenti

| Componente | Responsabilità | Non fa |
| --- | --- | --- |
| `orbit-api` | riceve le richieste HTTP, autentica il token, valida, crea il lease, legge lo stato reale a ogni richiesta, cancella stack e lease | non conserva token, non agisce senza una richiesta dell'utente |
| compito di creazione | dentro `orbit-api`, dopo la risposta: attende che la prenotazione sia attiva e crea lo stack col token della richiesta | non sopravvive a un riavvio del processo |
| tabella `orbs` | il legame fra orb, lease e stack, la taglia, lo stato osservato | non è la verità sulle risorse |

C'è un solo processo. Il lavoro dopo la risposta dura pochi secondi, il tempo che Blazar attivi la prenotazione, e usa il token della richiesta: un processo separato con una coda servirebbe solo se quel lavoro dovesse sopravvivere ai riavvii, e allora dovrebbe conservare una delega ([0002](adr/0002-risorse-nel-progetto-dell-utente.md)).

## Confine di proprietà

```
                     ┌──────────────── orbit ───────────────────────┐
  client  ──HTTP──▶  │  orbit-api  (+ compito di creazione)         │
                     │        tabella: orb, lease, stack, stato     │
                     └───────┬──────────────┬──────────────┬────────┘
                             │              │              │
                        Keystone         Blazar           Heat
                       (chi sei)       (capacità e      (quali risorse,
                                        flavor su        create e distrutte
                                        misura)          in ordine)
                                            │              │
                                          Nova          Nova, Neutron
```

Tutte le chiamate verso Blazar e Heat usano il token dell'utente. Il servizio non ha privilegi propri sulle risorse degli utenti.

Regole che non vanno violate perché sono il senso del progetto:

- **Il servizio non crea risorse da sé.** Non chiama Nova né Neutron in scrittura. La capacità e il flavor li crea Blazar, il resto Heat. Se un giorno serve una risorsa in più nell'orb, si aggiunge al template.
- **Il servizio non decide quando un orb finisce.** Lo decide il consumatore con `DELETE`. La data di fine del lease è fittizia ([0003](adr/0003-nessuna-scadenza.md)).
- **Il servizio non entra nell'orb.** Non esegue comandi, non copia file, non sa cosa ci gira. Consegna un indirizzo e un utente SSH.

## Sequenza di un orb

```
client            orbit-api                 Blazar               Heat
  │  POST /v1/orbs   │                         │                    │
  ├─────────────────▶│─ lease (taglia, ora,  ─▶│                    │
  │                  │   fine illimitata)      │─ crea il flavor    │
  │                  │◀─ reservation_id ───────┤                    │
  │  202 RESERVING   │                         │                    │
  │◀─────────────────┤                         │                    │
  │                  │ compito di creazione:   │                    │
  │                  │─ prenotazione attiva? ─▶│─ accesso al flavor │
  │                  │─ stack(flavor = reservation_id) ────────────▶│
  │                  │                         │                    │
  │  GET /v1/orbs/{id}                         │                    │
  ├─────────────────▶│─ stato di lease, stack e macchina ──────────▶│
  │  200 ACTIVE      │                         │                    │
  │◀─────────────────┤                         │                    │
  │                  │                         │                    │
  │  DELETE /v1/orbs/{id}                      │                    │
  ├─────────────────▶│─ cancella lo stack ────────────────────────▶│
  │                  │─ cancella il lease ────▶│─ distrugge la      │
  │  202 DELETING    │                         │  macchina, poi il  │
  │◀─────────────────┤                         │  flavor            │
```

Il passaggio che richiede attenzione è l'attesa fra lease e stack: il flavor della prenotazione esiste da subito, ma il progetto lo può usare solo quando la prenotazione è attiva ([0005](adr/0005-prenotazione-accanto-allo-stack.md)). Alla cancellazione, invece, l'ordine lo garantisce Blazar: distrugge la macchina, aspetta che non esista più, e solo allora cancella il flavor.

## Installazione

Il servizio si installa come plugin DevStack: un repository con una cartella `devstack/` contenente `settings` (che dichiara il plugin e abilita i servizi) e `plugin.sh`, chiamato nelle fasi `pre-install`, `install`, `post-config` ed `extra` di `stack.sh`, più `unstack` e `clean`.

Oltre ai propri processi, il plugin deve:

- dichiarare la dipendenza dai plugin di Heat e Blazar, che vanno abilitati prima nel `local.conf`;
- registrare servizio ed endpoint nel catalogo di Keystone;
- registrare l'host di calcolo in Blazar, senza il quale nessun lease è creabile;
- lasciare `max_lease_duration` di Blazar al valore predefinito `-1`, che non limita la durata dei lease.
