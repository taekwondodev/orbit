# La prenotazione si crea prima dello stack e resta fuori da esso

Il servizio crea il lease Blazar chiamando Blazar, attende che la prenotazione diventi attiva, e solo allora crea lo stack Heat passandogli il flavor della prenotazione. Il lease **non** è una risorsa del template, benché Heat offra `OS::Blazar::Lease` e metterlo dentro darebbe un solo oggetto da creare e da cancellare.

Il motivo è il rinnovo. Il codice di quella risorsa dichiara esplicitamente di non supportare l'aggiornamento, perché lo schema dei lease di Blazar non si presta: con il lease dentro il template, prolungare una sessione sarebbe impossibile se non scavalcando Heat e desincronizzando lo stack. Una sessione che non si può prolungare non è un lease, è un timer: un lavoro che dura più del previsto muore sotto le mani di chi lo sta facendo, e l'unica via d'uscita è ricostruire tutto.

## Alternativa scartata

**Il lease come risorsa del template.** Architettonicamente più pulita, un solo proprietario e una sola cancellazione, e difendibile se si dichiara la durata fissa come scelta esplicita. Scartata perché il rinnovo è la funzione che distingue questo servizio da uno script, e perché senza di essa il servizio si ridurrebbe quasi soltanto alla delega e alla pulizia.

## Conseguenze accettate

- Due oggetti per sessione, lease e stack, che vanno collegati e tenuti allineati: il legame vive nella tabella del servizio.
- La creazione diventa una sequenza con un'attesa in mezzo, perché il flavor della prenotazione esiste solo quando la prenotazione è attiva. Lo stato della sessione deve distinguere "sto prenotando" da "sto costruendo".
- Il rinnovo non passa mai da Heat: è una modifica della data di fine sul lease. Lo stack non ne viene toccato e non deve essere ricreato nel frattempo.

## Fonti

- `Lease.__doc__` di Heat: «this resource class does not support updating, because current Blazar lease scheme is not suitable for Heat» — <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/blazar/lease.py>
- Ciclo di una prenotazione di istanze e comparsa del flavor a prenotazione attiva: <https://docs.openstack.org/blazar/latest/cli/instance-reservation.html>
