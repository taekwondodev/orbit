# Gli orb nascono nel progetto di chi li chiede

Il servizio crea le risorse a nome del consumatore, inoltrando il token ricevuto nella richiesta, invece di possederle in un proprio progetto di servizio. Così l'isolamento fra utenti e il tetto massimo di macchine li fa rispettare OpenStack, non il nostro database: la quota del progetto risponde "no" senza che il servizio debba contare nulla, e l'utente vede i propri orb con i comandi OpenStack che già conosce.

## Alternativa scartata

**Un unico progetto di servizio proprietario di tutti gli orb.** Più semplice da configurare, una sola credenziale. Scartata perché sposta nel nostro database due cose che OpenStack sa già fare: l'appartenenza di una risorsa a un utente e il limite di consumo. Una violazione di quel database diventerebbe una confusione di proprietà fra utenti diversi.

## Conseguenza accettata

Il token dell'utente vale circa un'ora, e basta: poiché un orb non scade ([0003](0003-nessuna-scadenza.md)), ogni operazione sulle risorse dell'utente avviene durante una sua richiesta o nei secondi immediatamente successivi. L'unico lavoro che segue la risposta è l'attesa della prenotazione e la creazione dello stack ([0005](0005-prenotazione-accanto-allo-stack.md)), e usa il token della richiesta tenuto in memoria. Il servizio non conserva né token né deleghe, e non ha privilegi propri sulle risorse degli utenti.

Il prezzo è che un lavoro interrotto, per esempio da un riavvio del servizio durante l'attesa, non viene ripreso da solo: l'orb finisce in `ERROR` alla lettura successiva, e l'utente lo cancella e ne chiede un altro.

## Fonti

- Il problema delle operazioni differite e il modello di autorizzazione che Heat adotta per risolverlo: <https://docs.openstack.org/heat/latest/admin/auth-model.html>
