# Il lease si crea prima dello stack e resta fuori da esso

Il servizio crea il lease Blazar chiamando Blazar, attende che la prenotazione diventi attiva, e solo allora crea lo stack Heat passandogli il flavor della prenotazione. Il lease **non** è una risorsa del template, benché Heat offra `OS::Blazar::Lease` e metterlo dentro darebbe un solo oggetto da creare e da cancellare.

Il motivo è l'attesa. La risorsa di Heat considera il lease creato appena Blazar risponde, senza aspettare che la prenotazione sia attiva: il suo codice non definisce alcun controllo di completamento. Ma il progetto può usare il flavor della prenotazione solo dopo l'attivazione, quindi una macchina nello stesso stack verrebbe creata troppo presto e fallirebbe. Fuori dallo stack l'attesa è nostra, esplicita e osservabile.

## Alternativa scartata

**Il lease come risorsa del template**, con la macchina che dipende da esso. Un solo proprietario e una sola cancellazione, e Heat cancellerebbe da sé il lease dopo la macchina. Scartata perché funziona solo se l'attivazione precede la creazione della macchina per caso. Va riconsiderata se una versione futura di Heat aspettasse la prenotazione attiva.

## Conseguenze accettate

- Due oggetti per orb, lease e stack, collegati nella tabella del servizio.
- La creazione è una sequenza con un'attesa in mezzo, eseguita dopo la risposta `202` da un compito interno al processo `orbit-api`, che usa il token della richiesta tenuto in memoria ([0002](0002-risorse-nel-progetto-dell-utente.md)). Lo stato distingue "sto prenotando" da "sto costruendo".
- La cancellazione tocca entrambi: prima lo stack, poi il lease. Cancellando il lease Blazar distrugge comunque la macchina, quindi l'ordine conta per la pulizia di Heat, non per la capacità.

## Fonti

- `heat/engine/resources/openstack/blazar/lease.py`: definisce `handle_create` ma nessun `check_create_complete` — <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/blazar/lease.py>
- Accesso del progetto al flavor concesso in `on_start`: <https://opendev.org/openstack/blazar/src/branch/master/blazar/plugins/instances/instance_plugin.py>
