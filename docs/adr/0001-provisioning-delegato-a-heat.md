# Le risorse dell'orb le crea Heat, non il codice del servizio

Il servizio non chiama Neutron e non crea macchine con Nova: descrive l'orb in un template Heat e chiede a Heat di crearne uno stack. La ragione non è la quantità di codice risparmiato, ma il caso difficile: creare un orb sono quattro operazioni in fila, e quando la terza fallisce bisogna disfare le prime due sapendo che anche il disfacimento può fallire. È il punto in cui un provisioning scritto a mano lascia macchine accese che nessuno cancella più, e Heat lo risolve da anni.

L'unica chiamata diretta a Nova riguarda il flavor dell'orb, che non può stare nel template per i motivi scritti in [0004](0004-flavor-privato-per-ogni-orb.md).

## Alternativa scartata

**Orchestrazione diretta con `openstacksdk`**, cioè il servizio che crea chiave, firewall, porta e macchina una chiamata alla volta. Scartata perché avrebbe richiesto di scrivere, e di dimostrare corretti, il recupero dagli errori parziali e i tentativi ripetuti. È la scelta che dà più codice proprio, ed è legittima se si vuole che il cuore del progetto sia il provisioning; qui il cuore è l'orb come oggetto: taglia su misura, stato fedele alla realtà, cancellazione completa.

## Conseguenze accettate

- Il provisioning sparisce dal progetto: resta un template di poche decine di righe.
- Heat crea lo stack in modo asincrono e ne espone lo stato: il servizio non ha bisogno di un proprio processo che aspetti, gli basta leggere lo stack quando qualcuno chiede dell'orb.
- Heat va abilitato nell'installazione: non fa parte dell'insieme predefinito e si aggiunge come plugin, avviando i processi `h-eng`, `h-api` e `h-api-cfn`.

## Fonti

- Contratto dei plugin DevStack e fasi di `stack.sh`: <https://docs.openstack.org/devstack/latest/plugins.html>
- Abilitazione di Heat su DevStack (`enable_plugin heat https://opendev.org/openstack/heat`): <https://docs.openstack.org/heat/latest/getting_started/on_devstack.html>
