# Architettura

Chi fa cosa, dove passa il confine di proprietà e in che ordine avvengono le cose. Le scelte che hanno prodotto questa forma sono registrate in [docs/adr](adr/); qui si descrive il risultato.

## Componenti

| Componente | Responsabilità | Non fa |
| --- | --- | --- |
| `orbit-api` | riceve le richieste HTTP, autentica il token, valida, crea flavor e stack, legge lo stato reale a ogni richiesta e risponde | non agisce mai senza una richiesta dell'utente |
| `orbit-cleaner` | compito periodico: cancella i flavor degli orb che nessuna macchina usa più | non tocca stack né risorse dell'utente, non cambia lo stato degli orb |
| tabella `orbs` | il legame fra orb, flavor e stack, la taglia, lo stato osservato | non è la verità sulle risorse |

Non c'è un processo che esegua lavori lenti in sottofondo: le chiamate del servizio durano poco, perché l'unica attesa lunga, la costruzione delle risorse, la fa Heat in modo asincrono. Il servizio chiede, risponde `202`, e scopre l'esito alla lettura successiva.

## Confine di proprietà

```
                     ┌──────────────── orbit ───────────────────────┐
  client  ──HTTP──▶  │  api                          cleaner        │
                     │        tabella: orb, flavor, stack, stato    │
                     └───────┬──────────────┬──────────────┬────────┘
                             │              │              │
                        Keystone          Nova            Heat
                       (chi sei)       (flavor su       (quali risorse,
                                        misura, con      create e distrutte
                                        la credenziale   in ordine, col
                                        del servizio)    token dell'utente)
                                                              │
                                                        Nova, Neutron
```

Regole che non vanno violate perché sono il senso del progetto:

- **Il servizio non crea le risorse dell'utente.** Le descrive nel template e le fa creare a Heat. Se un giorno serve una risorsa in più nell'orb, si aggiunge al template.
- **La credenziale del servizio serve solo ai flavor.** Tutto ciò che sta nel progetto dell'utente si tocca col token dell'utente, durante la sua richiesta.
- **Il servizio non entra nell'orb.** Non esegue comandi, non copia file, non sa cosa ci gira. Consegna un indirizzo e un utente SSH.

## Sequenza di un orb

```
client              api                       Nova                Heat
  │  POST /v1/orbs   │                          │                   │
  ├─────────────────▶│─ flavor (credenziale) ──▶│                   │
  │                  │─ accesso al progetto ───▶│                   │
  │                  │─ stack(flavor) col token dell'utente ───────▶│
  │  202 BUILDING    │                          │                   │
  │◀─────────────────┤                          │◀── crea macchina ─┤
  │                  │                          │                   │
  │  GET /v1/orbs/{id}                          │                   │
  ├─────────────────▶│─ stato e output dello stack ────────────────▶│
  │                  │─ stato della macchina ──▶│                   │
  │  200 ACTIVE      │                          │                   │
  │◀─────────────────┤                          │                   │
  │                  │                          │                   │
  │  DELETE /v1/orbs/{id}                       │                   │
  ├─────────────────▶│─ cancella lo stack col token dell'utente ───▶│
  │  202 DELETING    │                          │◀─ distrugge ──────┤
  │◀─────────────────┤                          │                   │
  │                  │                          │                   │
  │       cleaner ──▶│─ nessuna macchina usa il flavor? cancellalo ▶│
```

Il passaggio che richiede attenzione è l'ultimo: lo stack si cancella subito, il flavor no, perché Nova sconsiglia di cancellare un flavor usato da una macchina ancora esistente. Il pulitore chiude il conto quando la macchina non c'è più, senza dipendere dal fatto che qualcuno rilegga l'orb.

## Installazione

Il servizio si installa come plugin DevStack: un repository con una cartella `devstack/` contenente `settings` (che dichiara il plugin e abilita i servizi) e `plugin.sh`, chiamato nelle fasi `pre-install`, `install`, `post-config` ed `extra` di `stack.sh`, più `unstack` e `clean`.

Oltre ai propri processi, il plugin deve:

- dichiarare la dipendenza dal plugin di Heat, che va abilitato prima nel `local.conf`;
- creare l'utente del servizio e registrare servizio ed endpoint nel catalogo di Keystone.
