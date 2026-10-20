# Un orb vive finché qualcuno non lo cancella

Un orb non ha un'ora di fine: nasce con `POST` e finisce con `DELETE`. "Effimero" significa che l'orb dura quanto il lavoro di chi l'ha chiesto e poi scompare per intero, macchina e risorse di contorno insieme; non significa che scada da sé. È il consumatore a sapere quando il lavoro è finito, non il servizio.

Il lease Blazar con cui l'orb prenota la capacità ([0004](0004-taglia-come-prenotazione-blazar.md)) ha una data di fine perché Blazar la esige, ma è fissata lontanissima: non è una scadenza e il servizio non la mostra.

## Alternative scartate

**Scadenza governata da Blazar**, il primo disegno: la fine del lease era l'ora di fine dell'orb, un rinnovo la spostava in avanti, e alla scadenza Blazar riprendeva la macchina. Scartata perché nessun requisito chiede la scadenza, e quella rete di sicurezza costava molto: una trust di Keystone conservata cifrata per agire dopo la scadenza del token, un pulitore per lo stack che Blazar lasciava dietro, il rinnovo da tenere allineato fra lease e stack, un processo separato per i lavori differiti. È la strada da rileggere se la scadenza tornasse un requisito: [il disegno completo è nella storia del repository](https://github.com/taekwondodev/orbit/tree/1739781/docs/adr).

**Scadenza scritta nel servizio**, con una colonna `expires_at` e un compito periodico che cancella ciò che è scaduto. Meno costosa, ma richiede comunque di agire sulle risorse dell'utente quando l'utente non c'è, e quindi una delega conservata.

## Rischio accettato

Un orb dimenticato resta acceso e trattiene la sua capacità prenotata finché qualcuno non lo cancella. Il limite è la quota del progetto ([0002](0002-risorse-nel-progetto-dell-utente.md)) e la capacità che Blazar ha da concedere: quando è esaurita, i nuovi orb vengono rifiutati, non costruiti a metà.
