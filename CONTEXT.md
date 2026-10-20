# Glossario di dominio

Termini usati nel codice, nei documenti e nei messaggi di commit. Dove un termine appartiene a un componente OpenStack, la colonna "proprietario" dice chi ne possiede la definizione: non siamo liberi di cambiargliela.

## Il dominio del servizio

| Termine | Significato | Proprietario |
| --- | --- | --- |
| **Sessione** | una sandbox assegnata a un consumatore per un tempo determinato, con la sua anagrafica e il suo stato | agentsession |
| **Sandbox** | l'insieme concreto delle risorse di una sessione: macchina, chiave, firewall, porta, indirizzo | Heat (come stack) |
| **Taglia** | processori, memoria e disco chiesti per la sessione | agentsession, tradotta in una prenotazione |
| **Scadenza** | il momento in cui la sandbox smette di esistere | Blazar (fine della prenotazione) |
| **Rinnovo** | lo spostamento in avanti della scadenza di una sessione viva | agentsession, eseguito su Blazar |
| **Consumatore** | l'utente Keystone che ha chiesto la sessione; nel caso d'uso originario è un agente | Keystone |
| **Pulitore** | il compito periodico che cancella gli stack delle sessioni il cui tempo è finito | agentsession |

Una sessione **non** è una macchina virtuale: è un diritto a usarne una fino a una certa ora. È la distinzione che rende il servizio diverso da uno script che chiama `openstack server create`.

## I componenti OpenStack e cosa ci mettiamo dentro

| Termine | Significato | Dove lo usiamo |
| --- | --- | --- |
| **Keystone** | identità, progetti, ruoli; rilascia i token | autentica le richieste e rilascia la delega |
| **Token** | prova temporanea di identità allegata a ogni richiesta; dura circa un'ora | arriva dal client, serve a creare le risorse a suo nome |
| **Progetto** | lo spazio a cui appartengono le risorse, con la sua quota | le sandbox nascono nel progetto del consumatore |
| **Trust** | delega registrata in Keystone: il *trustor* (utente) concede dei ruoli al *trustee* (il servizio), che ottiene un *trust ID* con cui chiedere token ristretti anche dopo | permette al pulitore di agire quando il token dell'utente è scaduto |
| **Nova** | accende, spegne e distrugge macchine virtuali | nessuna chiamata diretta: ci arriviamo tramite Heat e Blazar |
| **Neutron** | reti, porte, firewall, indirizzi raggiungibili | risorse dichiarate nel template |
| **Heat** | orchestrazione: legge un template e crea in ordine le risorse elencate, disfacendole se qualcosa fallisce | crea e distrugge la sandbox |
| **Stack** | l'insieme di risorse creato da Heat a partire da un template | una sandbox è uno stack |
| **Blazar** | prenotazione di risorse: concede capacità a un progetto fra un inizio e una fine, e la riprende alla scadenza | governa il tempo della sessione |
| **Lease** | per Blazar, l'accordo con inizio e fine; contiene una o più prenotazioni ed emette eventi, fra cui la propria fine | un lease per sessione |
| **Prenotazione** | la capacità concessa da un lease; per il tipo `virtual:instance` è descritta da `vcpus`, `memory_mb`, `disk_gb`, `amount` | è qui che finisce la taglia della sessione |
| **Flavor della prenotazione** | Blazar pubblica, finché la prenotazione è attiva, un flavor Nova non pubblico il cui identificativo coincide con quello della prenotazione | è il modo con cui la macchina si aggancia alla prenotazione |
| **DevStack** | installazione di OpenStack da sorgenti per sviluppo, estendibile con plugin | l'ambiente in cui il servizio viene installato e provato |

## Conflitti di terminologia da non creare

Blazar chiama **lease** il proprio accordo a tempo. Nel nostro dominio la parola corrispondente è **sessione**, e un lease è un suo attributo. Nei documenti e nel codice: `session` per il nostro concetto, `lease` solo quando si parla dell'oggetto Blazar.

Heat chiama **stack** l'insieme delle risorse. Nel nostro dominio si chiama **sandbox**. Nel codice, il campo che conserva l'identificativo si chiama `stack_id`, perché è l'identificativo di un oggetto di Heat.
