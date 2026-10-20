# Glossario di dominio

Termini usati nel codice, nei documenti e nei messaggi di commit. Dove un termine appartiene a un componente OpenStack, la colonna "proprietario" dice chi ne possiede la definizione: non siamo liberi di cambiargliela.

## Il dominio del servizio

| Termine | Significato | Proprietario |
| --- | --- | --- |
| **Orb** | una sandbox effimera: una macchina isolata, dimensionata su richiesta, raggiungibile in SSH, che vive finché qualcuno non la cancella | orbit |
| **Taglia** | processori, memoria e disco chiesti per un orb | orbit, tradotta in un flavor privato |
| **Flavor dell'orb** | il flavor Nova creato per un solo orb, non pubblico, accessibile solo al progetto del consumatore | Nova; lo crea e lo cancella orbit |
| **Consumatore** | l'utente Keystone che ha chiesto l'orb; nel caso d'uso originario è un agente | Keystone |
| **Pulitore** | il compito periodico che cancella i flavor degli orb non più usati da alcuna macchina | orbit |

Un orb **non** è una macchina virtuale: è l'insieme di macchina, chiave, firewall, porta e indirizzo, creati e distrutti insieme, più lo stato con cui il servizio li racconta. È la distinzione che rende il servizio diverso da uno script che chiama `openstack server create`.

Un orb non ha scadenza: la sua vita finisce con una richiesta di cancellazione. Vedi [docs/adr/0003](docs/adr/0003-nessuna-scadenza.md).

## I componenti OpenStack e cosa ci mettiamo dentro

| Termine | Significato | Dove lo usiamo |
| --- | --- | --- |
| **Keystone** | identità, progetti, ruoli; rilascia i token | autentica le richieste |
| **Token** | prova temporanea di identità allegata a ogni richiesta; dura circa un'ora | arriva dal client, serve a creare, leggere e cancellare le risorse a suo nome |
| **Progetto** | lo spazio a cui appartengono le risorse, con la sua quota | gli orb nascono nel progetto del consumatore |
| **Credenziale di servizio** | l'utente Keystone del servizio, nel progetto `service` | usata solo per creare, condividere e cancellare i flavor degli orb |
| **Nova** | accende, spegne e distrugge macchine virtuali; possiede i flavor | flavor dell'orb, chiamato direttamente; le macchine passano da Heat |
| **Flavor** | la descrizione di processori, memoria e disco con cui Nova crea una macchina; la gestione è riservata all'amministratore | uno per orb |
| **Neutron** | reti, porte, firewall, indirizzi raggiungibili | risorse dichiarate nel template |
| **Heat** | orchestrazione: legge un template e crea in ordine le risorse elencate, disfacendole se qualcosa fallisce | crea e distrugge le risorse dell'orb |
| **Stack** | l'insieme di risorse creato da Heat a partire da un template | le risorse di un orb sono uno stack |
| **DevStack** | installazione di OpenStack da sorgenti per sviluppo, estendibile con plugin | l'ambiente in cui il servizio viene installato e provato |

## Conflitti di terminologia da non creare

Heat chiama **stack** l'insieme delle risorse. Nel nostro dominio l'oggetto è l'**orb**, e lo stack è un suo attributo. Nel codice, il campo che conserva l'identificativo si chiama `stack_id`, perché è l'identificativo di un oggetto di Heat; lo stesso vale per `flavor_id`.

**Orbit** è il nome del servizio, **orb** il nome della risorsa che gestisce. Non usare "sessione", "sandbox" o "lease" per un orb.
