# Un orb vive finché qualcuno non lo cancella

Un orb non ha un'ora di fine: nasce con `POST` e finisce con `DELETE`. "Effimero" significa che l'orb dura quanto il lavoro di chi l'ha chiesto e poi scompare per intero, macchina e risorse di contorno insieme; non significa che scada da sé. È il consumatore a sapere quando il lavoro è finito, non il servizio.

## Alternative scartate

**Scadenza governata da Blazar**, il disegno precedente: ogni orb diventava un lease con taglia e ora di fine, Blazar riprendeva la macchina alla scadenza, un rinnovo spostava la fine in avanti. Scartata perché il costo era sproporzionato a una rete di sicurezza: un terzo componente da installare con l'host di calcolo registrato, un'attesa fra prenotazione e creazione (il flavor della prenotazione esiste solo quando è attiva), una trust di Keystone conservata cifrata per agire dopo la scadenza del token, un pulitore per lo stack che Blazar lasciava dietro, e due oggetti per orb da tenere allineati. È la strada da rileggere se la scadenza tornasse un requisito: [il disegno completo è nella storia del repository](https://github.com/taekwondodev/orbit/tree/1739781/docs/adr).

**Scadenza scritta nel servizio**, con una colonna `expires_at` e un compito periodico che cancella ciò che è scaduto. Meno costosa, ma richiede comunque di agire sulle risorse dell'utente quando l'utente non c'è, e quindi una delega conservata. Scartata perché nessun requisito chiede la scadenza.

## Rischio accettato

Un orb dimenticato resta acceso e consuma la quota del progetto finché qualcuno non lo cancella. Il limite è la quota stessa ([0002](0002-risorse-nel-progetto-dell-utente.md)): un progetto non può accumulare più macchine di quante OpenStack gliene conceda.
