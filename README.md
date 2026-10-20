# orbit

**Sandbox effimere come servizio OpenStack.** Un client chiede "una macchina con queste risorse"; il servizio gliela consegna isolata e raggiungibile in SSH, e quando il client ha finito la fa sparire per intero. Ogni sandbox è un **orb**.

---

## Scheda

| | |
| --- | --- |
| **Tipo** | nuovo servizio OpenStack, non un'estensione di un servizio esistente |
| **Ambiente** | DevStack, installato tramite plugin |
| **Linguaggio** | Python |
| **Componenti integrati** | Keystone, Heat, Nova; Neutron tramite Heat |
| **Interfacce** | API REST, plugin per `openstack` da riga di comando |
| **Risorsa gestita** | l'*orb*: una macchina isolata, dimensionata su richiesta, con le sue risorse di contorno |
| **Stato** | progettazione conclusa, implementazione da iniziare |

---

## Il problema

Chi esegue lavori non fidati o distruttivi — compilazioni, test, un agente che modifica un repository — ha bisogno di una macchina intera, non di una cartella. Quella macchina deve essere **isolata**, **dimensionata sul lavoro** e, quando il lavoro finisce, deve sparire **senza lasciare niente dietro**: né la macchina, né la chiave, né il firewall, né l'indirizzo.

Fatto a mano, con una manciata di comandi `openstack`, ognuno di questi punti si rompe: le taglie disponibili sono quelle del catalogo, una creazione fallita a metà lascia pezzi sparsi, una cancellazione dimenticata lascia un indirizzo occupato. `orbit` tratta la sandbox come un oggetto unico, l'orb, che nasce intero e muore intero.

## Cosa fa

- Accetta la **taglia** richiesta — processori, memoria, disco — orb per orb, senza cataloghi di dimensioni prefissate.
- Crea l'orb nel **progetto di chi lo chiede**: compare fra le sue risorse e consuma la sua quota.
- Installa la **chiave pubblica fornita dal client** e restituisce indirizzo e utente per l'accesso SSH.
- **Cancella tutto** con una sola richiesta, ripetibile senza errore.
- **Dice la verità** sullo stato: ogni lettura guarda le risorse reali, quindi una macchina cancellata a mano non lascia un orb che mente.

## Cosa non fa

Non entra nell'orb: non esegue comandi, non copia file, non sa cosa ci gira dentro. Consegna un indirizzo e si fa da parte. Non decide quando un orb deve finire: lo decide chi l'ha chiesto. Non prepara immagini, non fa da proxy, non gestisce più di una macchina per orb.

---

## Architettura

```mermaid
flowchart LR
    client["Client<br/>riga di comando, script, agente"]

    subgraph svc["orbit"]
        direction TB
        api["orbit-api<br/>autentica, crea, legge lo stato reale"]
        cln["orbit-cleaner<br/>rimuove i flavor non più usati"]
        db[("tabella<br/>orbs")]
    end

    ks["Keystone<br/>identità"]
    nova["Nova<br/>flavor su misura"]
    heat["Heat<br/>risorse dell'orb"]
    infra["Nova + Neutron<br/>macchina, rete, firewall"]

    client -->|HTTP| api
    api --- db
    cln --- db
    api --> ks
    api -->|credenziale del servizio| nova
    cln -->|credenziale del servizio| nova
    api -->|token dell'utente| heat
    heat --> infra
```

Il servizio **non crea le risorse dell'utente**: le descrive in un template e le fa creare a Heat, col token di chi le chiede. L'unica cosa che crea da sé è il flavor su misura, perché Nova riserva i flavor all'amministratore: per quello, e solo per quello, usa la propria credenziale.

| Processo | Responsabilità |
| --- | --- |
| `orbit-api` | riceve le richieste, verifica il token, valida la taglia, crea flavor e stack, rilegge lo stato reale a ogni richiesta |
| `orbit-cleaner` | cancella i flavor degli orb rimossi, quando nessuna macchina li usa più |

---

## Ciclo di vita di un orb

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant A as orbit
    participant N as Nova
    participant H as Heat

    C->>A: POST /v1/orbs con taglia e chiave pubblica
    A->>N: crea il flavor privato orbit-id
    A->>N: concedine l'accesso al progetto del client
    A->>H: crea lo stack col token del client
    A-->>C: 202 Accepted, orb in BUILDING

    C->>A: GET /v1/orbs/{id}
    A->>H: stato e indirizzo dello stack
    A->>N: la macchina esiste ed è accesa?
    A-->>C: ACTIVE, indirizzo e utente SSH

    C->>A: DELETE /v1/orbs/{id}
    A->>H: cancella lo stack col token del client
    A-->>C: 202 Accepted, orb in DELETING

    Note over A,N: più tardi, il pulitore
    A->>N: nessuna macchina usa il flavor: cancellalo
```

Lo stack e il flavor si cancellano in due momenti diversi perché Nova sconsiglia di cancellare un flavor mentre una macchina lo usa. Il pulitore chiude il conto quando la macchina non c'è più.

---

## Stati di un orb

```mermaid
stateDiagram-v2
    direction LR
    [*] --> BUILDING
    BUILDING --> ACTIVE: macchina pronta
    ACTIVE --> DELETING: cancellazione
    BUILDING --> DELETING: cancellazione
    DELETING --> DELETED
    DELETED --> [*]

    BUILDING --> ERROR: costruzione fallita
    ACTIVE --> ERROR: cambiato da fuori
    DELETING --> ERROR: cancellazione fallita
    ERROR --> DELETING: cancellazione esplicita
```

Lo stato non lo decide il servizio: lo osserva. Ogni lettura chiede a Heat e a Nova com'è davvero l'orb e corregge la tabella. Un orb in `ERROR` non si cancella da sé: le risorse restano osservabili finché qualcuno non chiede esplicitamente di rimuoverle.

---

## Interfaccia

| Metodo e percorso | Effetto |
| --- | --- |
| `POST /v1/orbs` | chiede un orb; risponde subito, la costruzione continua in Heat |
| `GET /v1/orbs` | elenca gli orb del proprio progetto |
| `GET /v1/orbs/{id}` | stato, indirizzo SSH, eventuale motivo dell'errore |
| `DELETE /v1/orbs/{id}` | fa sparire l'orb; ripetibile senza errore |

```jsonc
// POST /v1/orbs
{
  "size": { "vcpus": 2, "memory_mb": 4096, "disk_gb": 20 },
  "public_key": "ssh-ed25519 AAAA...",
  "image": "ubuntu-24.04"
}
```

Il contratto completo, con codici di errore e transizioni, è in [docs/design/api.md](docs/design/api.md).

---

## Documenti

| Documento | Contenuto |
| --- | --- |
| [CONTEXT](CONTEXT.md) | glossario del dominio e dei termini OpenStack usati |
| [Architettura](docs/architettura.md) | confini di proprietà, sequenza completa, requisiti di installazione |
| [Contratto della API](docs/design/api.md) | risorse HTTP, stati, errori |
| [Stato conservato](docs/design/stato.md) | la tabella del servizio, il riallineamento, il pulitore |
| [Template dell'orb](templates/orb.yaml) | descrizione Heat delle risorse di un orb |
| [Decisioni](docs/adr/) | le quattro scelte di forma, con motivazione e fonti |

## Stato dei lavori

- [x] Decisioni di forma registrate, con fonti verificate
- [x] Contratto della API, stati e schema dei dati
- [x] Template dell'orb
- [ ] Plugin DevStack e scheletro eseguibile del servizio
- [ ] Flavor su misura e creazione dello stack
- [ ] Lettura dello stato reale e cancellazione
- [ ] Pulitore dei flavor
- [ ] Plugin per `openstack` da riga di comando
- [ ] Test automatici

Nessun componente è stato ancora installato: tutte le affermazioni tecniche nei documenti sono tratte dalla documentazione ufficiale o dal codice sorgente di OpenStack, con il collegamento alla fonte accanto.
