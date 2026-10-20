# Ogni orb ha la sua rete e il suo router

Il template di un orb crea, oltre alla macchina e alle risorse di contorno, una rete con la sua sottorete e un router collegato alla rete esterna. L'orb non si appoggia a una rete esistente del progetto: nasce e muore con la propria, insieme al resto dello stack ([0001](0001-provisioning-delegato-a-heat.md)).

Così un orb è isolato anche a livello di rete, non solo dal firewall: non condivide il segmento con altre macchine, neppure dello stesso progetto. E funziona in qualunque progetto senza preparazione, perché non dipende da una rete che il progetto deve già avere. Gli orb usano tutti lo stesso intervallo di indirizzi, ciascuno dietro il proprio router.

## Alternative scartate

**Una rete di progetto indicata in configurazione**, il disegno iniziale. In DevStack la rete `private` appartiene al progetto `demo`, e Heat risolve il nome col token di chi chiede: per qualunque altro progetto la rete non esiste e lo stack fallisce. Il servizio avrebbe funzionato solo per un progetto.

**Una rete scelta dal client nella richiesta**, con il valore configurato come predefinito. Modifica piccola, ma sposta sul client il compito di avere una rete con un router verso l'esterno, e la macchina dividerebbe la rete con le altre del progetto.

**Una rete condivisa preparata dall'amministratore** per tutti i progetti. Una sola rete da gestire, ma orb di utenti diversi starebbero sullo stesso segmento, protetti solo dal firewall.

## Conseguenze accettate

- **Un router per orb, e quindi un tetto per progetto.** Neutron limita per default ogni progetto a 10 router e 10 security group; ogni orb ne usa uno per tipo, e il security group `default` del progetto conta nella quota. Con i valori predefiniti un progetto tiene circa 9 orb contemporanei. Sono quote per progetto e l'amministratore le alza quando vuole, per esempio con `openstack quota set --routers 50 --secgroups 50 <progetto>`. Quando una quota è esaurita, Heat rifiuta lo stack e l'orb va in `ERROR` col motivo di Neutron ([0002](0002-risorse-nel-progetto-dell-utente.md)).
- **Creazione un po' più lunga**: rete, sottorete, router e interfaccia precedono la porta e l'indirizzo esterno, che si può associare solo a una porta raggiungibile dal router.
- **Il servizio non configura più reti di progetto**: resta solo la rete esterna, `[orbs] public_network`.

## Fonti

- Quote predefinite di Neutron, `DEFAULT_QUOTA_ROUTER = 10` e `DEFAULT_QUOTA_SG = 10`: <https://opendev.org/openstack/neutron/src/branch/master/neutron/conf/quota.py>
- Il security group `default` conta nella quota: il plugin ML2 traccia i security group col modello `SecurityGroup` e l'uso si conta come righe filtrate solo per `project_id`, senza escludere `is_default`: <https://opendev.org/openstack/neutron/src/branch/master/neutron/plugins/ml2/plugin.py> (`tracked_resources`), <https://opendev.org/openstack/neutron/src/branch/master/neutron/quota/resource.py> (`TrackedResource.count_used`)
- Risorse Heat `OS::Neutron::Router` (`external_gateway_info.network`), `OS::Neutron::RouterInterface`, `OS::Neutron::Subnet`: <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/neutron>
