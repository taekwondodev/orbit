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

![Architettura: il client parla con orbit-api; orbit chiede capacità e flavor a Blazar e le risorse a Heat col token dell'utente, e legge soltanto da Nova](img/architettura.svg)

Tutte le chiamate verso Blazar e Heat usano il token dell'utente. Il servizio non ha privilegi propri sulle risorse degli utenti.

La regola che non va violata perché è il senso del progetto: **il servizio non crea risorse da sé.** Non chiama Nova né Neutron in scrittura. La capacità e il flavor li crea Blazar, il resto Heat. Se un giorno serve una risorsa in più nell'orb, si aggiunge al template.

Cosa il servizio non fa, come entrare nell'orb o decidere quando finisce, è nel [README](../README.md#cosa-non-fa).

## Sequenza di un orb

Le chiamate fra client, orbit, Blazar e Heat sono nel diagramma di sequenza del [README](../README.md#ciclo-di-vita-di-un-orb); qui, cosa succede nel tempo e cosa distrugge chi.

![Creazione: le due attese e il limite creation_timeout](img/creazione.svg)

![Cancellazione: prima lo stack, poi il lease](img/cancellazione.svg)

Il passaggio che richiede attenzione è l'attesa fra lease e stack: il flavor della prenotazione esiste da subito, ma il progetto lo può usare solo quando la prenotazione è attiva ([0005](adr/0005-prenotazione-accanto-allo-stack.md)). Alla cancellazione, invece, l'ordine lo garantisce Blazar: distrugge la macchina, aspetta che non esista più, e solo allora cancella il flavor.

## Installazione

![Installazione: cosa fanno i plugin di Heat, Blazar e orbit in ogni fase di stack.sh](img/installazione.svg)

Il servizio si installa come plugin DevStack: un repository con una cartella `devstack/` contenente `settings` (che dichiara il plugin e abilita i servizi) e `plugin.sh`, chiamato nelle fasi `install`, `post-config` ed `extra` di `stack.sh`, più `unstack` e `clean`.

Oltre ai propri processi, il plugin deve:

- dichiarare la dipendenza dai plugin di Heat e Blazar, che vanno abilitati prima nel `local.conf`;
- registrare servizio ed endpoint nel catalogo di Keystone;
- registrare l'host di calcolo in Blazar, senza il quale nessun lease è creabile;
- lasciare `max_lease_duration` di Blazar al valore predefinito `-1`, che non limita la durata dei lease.

La registrazione dell'host avviene nella fase `extra`, ma DevStack mappa gli host nella cella di Nova solo dopo quella fase, e la API di Nova non mostra gli hypervisor non mappati. Il plugin esegue quindi `nova-manage cell_v2 discover_hosts`, ripetibile, prima di cercarli.

Con l'host registrato, il filtro `BlazarFilter` di Nova lo riserva alle prenotazioni: una richiesta senza prenotazione non passa su un host che appartiene a un aggregato di Blazar, compreso `freepool`. Su un DevStack con un solo host, le macchine create fuori da orbit non trovano posto. Fonte: `host_passes` in <https://opendev.org/openstack/blazar-nova/src/branch/master/blazarnova/scheduler/filters/blazar_filter.py>
