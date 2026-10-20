# La taglia di un orb è una prenotazione Blazar a fine illimitata

Per ogni orb il servizio crea, col token del consumatore, un lease Blazar di tipo `virtual:instance` con i processori, la memoria e il disco richiesti, inizio "adesso" e una data di fine lontanissima. Blazar crea per quella prenotazione un flavor non pubblico, lo rende accessibile al solo progetto del consumatore e, quando il lease viene cancellato, distrugge le macchine che lo usano, aspetta che non esistano più e cancella il flavor.

Così la taglia su misura non richiede privilegi al servizio, e la cancellazione del flavor avviene nell'ordine giusto senza un pulitore nostro. Blazar si usa qui per la capacità e per il flavor, non per il tempo ([0003](0003-nessuna-scadenza.md)).

## Alternative scartate

**Un flavor privato creato dal servizio** per ogni orb, il disegno del commit `eb7ee88`. Creare un flavor e concederne l'accesso sono operazioni riservate all'amministratore nella politica predefinita di Nova, quindi il servizio avrebbe avuto bisogno di una credenziale amministrativa, e di un pulitore proprio per cancellare il flavor solo dopo la macchina, perché Nova sconsiglia di cancellare un flavor in uso. Blazar fa entrambe le cose con le sue credenziali e il suo codice.

**Un catalogo di flavor prefissati**, con la taglia arrotondata al più vicino. Nessun privilegio e nessun componente in più, ma tradisce il requisito "ogni orb con risorse diverse".

**Il flavor dentro il template**, con `OS::Nova::Flavor`: Heat stesso avverte che la risorsa è utilizzabile solo da amministratori, e lo stack nasce col token del consumatore.

## Conseguenze accettate

- **Data di fine fittizia.** Blazar esige una fine; il servizio la fissa a un valore configurato lontanissimo. Blazar non pone un limite alla durata finché `max_lease_duration` resta al valore predefinito `-1`: l'installazione deve lasciarlo così.
- **Attesa prima della costruzione.** Il flavor esiste dalla creazione del lease, ma il progetto vi accede solo quando la prenotazione diventa attiva, cioè al successivo giro del ciclo di eventi di Blazar, che gira ogni dieci secondi. Lo stack si crea dopo: l'orb ha uno stato `RESERVING` distinto da `BUILDING`.
- **Capacità verificata subito.** Se nessun host ha posto per la taglia, Blazar rifiuta la creazione del lease: l'orb fallisce prima di costruire qualunque cosa.
- **Installazione più pesante.** Servono i pacchetti `blazar`, `blazar-nova` e `python-blazarclient`, e nessun lease è creabile finché l'host di calcolo non è stato registrato in Blazar (`openstack reservation host create <host>`): la registrazione entra nel plugin di installazione.

## Fonti

- Creazione del flavor non pubblico per la prenotazione, accesso al progetto in `on_start`, cancellazione delle macchine e poi del flavor in `on_end`: <https://opendev.org/openstack/blazar/src/branch/master/blazar/plugins/instances/instance_plugin.py>
- `delete_lease` esegue `on_end` anche su un lease attivo; `start_date` accetta `now`; ciclo degli eventi ogni 10 secondi (`EVENT_INTERVAL`): <https://opendev.org/openstack/blazar/src/branch/master/blazar/manager/service.py>
- Politiche di Blazar, `blazar:leases:post` e `:delete` valgono `rule:project_member_or_admin`: <https://docs.openstack.org/blazar/latest/configuration/blazar-policy.html>
- `max_lease_duration`, predefinito `-1` cioè nessun limite: <https://docs.openstack.org/blazar/latest/configuration/blazar-conf.html>
- Procedura di prenotazione di istanze e registrazione dell'host: <https://docs.openstack.org/blazar/latest/cli/instance-reservation.html>
- Politiche predefinite di Nova sui flavor, `rule:context_is_admin`: <https://docs.openstack.org/nova/latest/configuration/policy.html>
- `OS::Nova::Flavor`, «limited to being used by administrators only»: <https://docs.openstack.org/heat/latest/template_guide/openstack.html#OS::Nova::Flavor>
