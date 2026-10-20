# Le risorse dell'orb le crea Heat, non il codice del servizio

Il servizio non chiama Nova e Neutron per costruire un orb: descrive le risorse in un template Heat e chiede a Heat di crearne uno stack. La ragione non è la quantità di codice risparmiato, ma il caso difficile: creare un orb sono quattro operazioni in fila, e quando la terza fallisce bisogna disfare le prime due sapendo che anche il disfacimento può fallire. È il punto in cui un provisioning scritto a mano lascia macchine accese che nessuno cancella più, e Heat lo risolve da anni.

La sola risorsa che non sta nel template è il lease Blazar: il motivo è in [0005](0005-prenotazione-accanto-allo-stack.md).

## Alternativa scartata

**Orchestrazione diretta con `openstacksdk`**, cioè il servizio che crea chiave, firewall, porta e macchina una chiamata alla volta. Scartata perché avrebbe richiesto di scrivere, e di dimostrare corretti, il recupero dagli errori parziali e i tentativi ripetuti. È la scelta che dà più codice proprio, ed è legittima se si vuole che il cuore del progetto sia il provisioning; qui il cuore è l'orb come oggetto: capacità prenotata, stato fedele alla realtà, cancellazione completa.

## Conseguenze accettate

- Il provisioning sparisce dal progetto: resta un template di poche decine di righe.
- Heat crea lo stack in modo asincrono e ne espone lo stato: il servizio non aspetta la costruzione, la scopre leggendo lo stack quando qualcuno chiede dell'orb.
- Heat va abilitato nell'installazione: non fa parte dell'insieme predefinito e si aggiunge come plugin, avviando i processi `h-eng`, `h-api` e `h-api-cfn`.

## Fonti

- Contratto dei plugin DevStack e fasi di `stack.sh`: <https://docs.openstack.org/devstack/latest/plugins.html>
- Abilitazione di Heat su DevStack (`enable_plugin heat https://opendev.org/openstack/heat`): <https://docs.openstack.org/heat/latest/getting_started/on_devstack.html>
