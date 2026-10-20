# La durata di una sessione è una prenotazione Blazar

La taglia e la scadenza di una sessione diventano un lease Blazar di tipo `virtual:instance`: il servizio dichiara processori, memoria, disco e ora di fine, e Blazar concede la capacità e la riprende quando il tempo scade. Il servizio non implementa né un contatore di scadenze né la terminazione delle macchine: adotta il componente OpenStack il cui dominio è esattamente questo, dove *lease*, *reservation* ed *event* sono termini definiti dal suo glossario.

La taglia si esprime direttamente nella prenotazione, senza preparare a mano una serie di flavor: è il modo più diretto per sostenere il requisito "ogni sessione con risorse diverse".

## Alternativa scartata

**Scadenza e terminazione scritte nel servizio**, con una colonna `expires_at` e un compito periodico che cancella ciò che è scaduto. È meno codice di quanto sembri ed evita un terzo componente da installare; è stata scartata applicando il criterio "se esiste, lo usiamo".

## Rischio noto accettato

Blazar e Heat si sovrappongono: alla scadenza Blazar termina la macchina prenotata, ma non sa nulla dello stack che la conteneva, e nessuno avvisa Heat. La pulizia dello stack resta quindi un compito del servizio, ed è il punto in cui è più facile lasciare risorse appese. Questo attrito era la ragione per cui la scelta era stata inizialmente sconsigliata; la raccomandazione è caduta quando si è verificato che Heat ha un tipo di risorsa nativo per i lease Blazar dal rilascio Stein, cioè che la composizione fra i due è prevista e non improvvisata.

## Vincoli operativi che ne derivano

- Nessun lease è creabile finché l'host di calcolo non è stato registrato in Blazar (`openstack reservation host create <host>`): la validazione fallisce con "non trovo nessun host". La registrazione deve entrare nel plugin di installazione.
- Servono i pacchetti `blazar`, `blazar-nova` e `python-blazarclient`.
- Il flavor che rappresenta la prenotazione esiste **solo mentre la prenotazione è attiva**, si chiama `reservation:<id>` e non è pubblico. La macchina può quindi essere creata solo dopo che la prenotazione è diventata attiva, il che impone un'attesa fra la creazione del lease e quella dello stack.

## Fonti

- Glossario di Blazar (lease, reservation, event) e risorse prenotabili: <https://docs.openstack.org/blazar/latest/user/introduction.html>
- Procedura completa di prenotazione di istanze, freepool, campi della prenotazione, flavor `reservation:<id>`: <https://docs.openstack.org/blazar/latest/cli/instance-reservation.html>
- Risorsa Heat `OS::Blazar::Lease`, disponibile dalla versione 12.0.0, e sua validazione che richiede un host registrato: <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/blazar/lease.py>
