from django_unicorn.components import UnicornView
from datetime import datetime
from django.utils import timezone
from ..views import get_highest_bid_from_redis
import redis, os, json, hashlib
from ..models import Lot
from django.core import serializers
from ..utils import sendTransaction

redis_client = redis.Redis.from_url(os.environ.get('REDIS_LOCATION'))

class LotpriceView(UnicornView):
    price = 0
    duration = '0'

    def update(self):
        pk = self.component_kwargs["pk"]
        if redis_client.get(f"lot:{pk}:status").decode('ascii') == "open":
            try:
                self.price = get_highest_bid_from_redis(f"lot:{pk}:bids")[1]
            except:
                pass

            current_time = timezone.now()

            # verifica se l'asta è già iniziata
            if current_time > self.component_kwargs["lotStartAuction"]:
                # calcolo tempo rimanente dell'asta
                endAuction_str = redis_client.get(f"lot:{pk}:endAuction")
                endAuction = datetime.strptime(endAuction_str.decode('ascii'), '%Y-%m-%d %H:%M:%S.%f%z')

                self.duration = str(endAuction - current_time).split('.')[0]

            # chiusura asta
            if self.duration < '0':
                self.duration = 0

                lot = Lot.objects.get(pk=pk)
                if lot.status == "open":
                    lot.status = "closed"
                    lot.price = self.price
                    lot.winner = get_highest_bid_from_redis(f"lot:{pk}:bids")[0]
                    lot.save()
                
                    redis_client.set(f'lot:{pk}:status', "closed")

                # Creare json con dettagli asta
                data = serializers.serialize('json', [lot]) # serializza l'istanza in formato JSON
                
                with open(f'jsonfiles/lot_{pk}.json', 'w') as json_file: # scrivi il JSON in un file
                    json_file.write(data)

                # Apri il file JSON precedentemente creato 
                with open(f'jsonfiles/lot_{pk}.json', 'r') as json_file: 
                    json_data = json_file.read()

                # calcola l'hash del contenuto JSON
                hash_object = hashlib.sha256(json_data.encode())
                hash = hash_object.hexdigest()

                # inviamo l'hash come transazione sulla rete Ethereum
                txId = sendTransaction(hash)

                # salvataggio hash e txid sul database
                lot.hash = hash
                lot.txId = txId
                lot.save()
