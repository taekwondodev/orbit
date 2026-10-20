# Glossario di dominio

Termini usati nel codice, nei documenti e nei messaggi di commit. Dove un termine appartiene a un componente OpenStack, la colonna "proprietario" dice chi ne possiede la definizione: non siamo liberi di cambiargliela.

## Il dominio del servizio

| Termine | Significato | Proprietario |
| --- | --- | --- |
| **Orb** | una sandbox effimera: una macchina isolata, dimensionata su richiesta, raggiungibile in SSH, che vive finché qualcuno non la cancella | orbit |
| **Taglia** | processori, memoria e disco chiesti per un orb | orbit, tradotta in una prenotazione Blazar |
| **Consumatore** | l'utente Keystone che ha chiesto l'orb; nel caso d'uso originario è un agente | Keystone |

Un orb **non** è una macchina virtuale: è l'insieme di prenotazione, rete, router, macchina, chiave, firewall, porta e indirizzo, creati e distrutti insieme, più lo stato con cui il servizio li racconta. È la distinzione che rende il servizio diverso da uno script che chiama `openstack server create`.

Un orb non ha scadenza: la sua vita finisce con una richiesta di cancellazione. Vedi [docs/adr/0003](docs/adr/0003-nessuna-scadenza.md).

## I componenti OpenStack e cosa ci mettiamo dentro

| Termine | Significato | Dove lo usiamo |
| --- | --- | --- |
| **Keystone** | identità, progetti, ruoli; rilascia i token | autentica le richieste |
| **Token** | prova temporanea di identità allegata a ogni richiesta; dura circa un'ora | arriva dal client, serve a creare, leggere e cancellare le risorse a suo nome; il servizio non lo conserva |
| **Progetto** | lo spazio a cui appartengono le risorse, con la sua quota | gli orb nascono nel progetto del consumatore |
| **Blazar** | prenotazione di risorse: concede capacità a un progetto fra un inizio e una fine, e la riprende alla fine o alla cancellazione | trasforma la taglia in capacità garantita e in un flavor su misura |
| **Lease** | per Blazar, l'accordo con inizio e fine; contiene una o più prenotazioni | un lease per orb, con inizio "adesso" e fine illimitata |
| **Prenotazione** | la capacità concessa da un lease; per il tipo `virtual:instance` è descritta da `vcpus`, `memory_mb`, `disk_gb`, `amount` | è qui che finisce la taglia dell'orb |
| **Flavor della prenotazione** | il flavor Nova non pubblico che Blazar crea per la prenotazione, con lo stesso identificativo; il progetto vi accede solo quando la prenotazione è attiva, e Blazar lo cancella con il lease | la macchina dell'orb usa questo flavor |
| **Fine illimitata** | la data di fine del lease, fissata lontanissima perché Blazar la esige ma l'orb non scade | non è una scadenza: l'orb finisce con `DELETE` |
| **Nova** | accende, spegne e distrugge macchine virtuali | nessuna chiamata di scrittura: ci arriviamo tramite Heat e Blazar |
| **Neutron** | reti, porte, firewall, indirizzi raggiungibili | risorse dichiarate nel template |
| **Heat** | orchestrazione: legge un template e crea in ordine le risorse elencate, disfacendole se qualcosa fallisce | crea e distrugge le risorse dell'orb tranne il lease |
| **Stack** | l'insieme di risorse creato da Heat a partire da un template | le risorse di un orb, lease escluso, sono uno stack |
| **DevStack** | installazione di OpenStack da sorgenti per sviluppo, estendibile con plugin | l'ambiente in cui il servizio viene installato e provato |

## Conflitti di terminologia da non creare

Blazar chiama **lease** il proprio accordo a tempo. Per noi un lease non è un orb né una scadenza: è un attributo dell'orb, l'oggetto Blazar che ne garantisce la capacità. Nel codice: `lease` e `reservation` solo per gli oggetti Blazar.

Heat chiama **stack** l'insieme delle risorse. Nel nostro dominio l'oggetto è l'**orb**, e lo stack è un suo attributo. Nel codice, i campi che conservano gli identificativi si chiamano `lease_id`, `reservation_id` e `stack_id`, perché sono identificativi di oggetti altrui.

**Orbit** è il nome del servizio, **orb** il nome della risorsa che gestisce. Non usare "sessione" o "sandbox" per un orb.
