from django.db import models
from django.utils import timezone
from datetime import timedelta
import redis, os
from datetime import datetime
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver


def upload_profile_pics(instance, filename):
    return os.path.join(f'images/users/{instance.user.username}', 'profile_pics.jpg')

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='images/users/default_profile.png', upload_to=upload_profile_pics)

    def __str__(self):
        return self.user.username

@receiver(pre_save, sender=Profile)
def profile_pre_save(sender, instance, **kwargs):
    try:
        old_profile = sender.objects.get(pk=instance.pk)
        
        # Verifica se l'immagine del profilo è cambiata
        if old_profile.image != instance.image:
            # elimina l'immagine precedente
            old_profile.image.delete(save=False)
    except sender.DoesNotExist:
        pass


def upload_to(instance, filename):
    return os.path.join('images/lots/', str(instance.id), filename)

class Lot(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=800)
    category = models.CharField(max_length=10, choices=[('car', 'car'), ('motorcycle', 'motorcycle'), ('scooters', 'scooters')], default='car')
    img = models.ImageField(upload_to=upload_to)
    startingPrice = models.FloatField()
    startAuction = models.DateTimeField(default=timezone.now)
    duration = models.IntegerField(default=60, blank=True)
    endAuction = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=6, choices=[('open', 'open'), ('closed', 'closed')], default='open')
    winner = models.CharField(max_length=20, blank=True, null=True)
    price = models.FloatField(blank=True, null=True)
    hash = models.CharField(max_length=20, default=None, blank=True, null=True)
    txId = models.CharField(max_length=80, default=None, blank=True, null=True)

    def __str__(self):
        return str(self.id)
    
    def save(self, *args, **kwargs):
        # Salvataggio stato e data fine asta su redis
        def redis_variable():
            redis_client = redis.Redis.from_url(os.environ.get('REDIS_LOCATION'))
            endAuction_str = self.endAuction.strftime('%Y-%m-%d %H:%M:%S.%f%z')
            redis_client.set(f'lot:{self.id}:endAuction', endAuction_str)
            redis_client.lpush(f'lot:{self.id}:bids', f"admin|{self.startingPrice}|{timezone.now()}")
            redis_client.set(f'lot:{self.id}:status', "open")

        # calcolo data fine asta
        if not self.endAuction:
            self.endAuction = self.startAuction + timedelta(minutes=self.duration)
            redis_variable()

        # calcolo durata minuti asta
        if not self.duration:
            self.duration = (self.endAuction - self.startAuction).total_seconds() // 60
            redis_variable()

        super().save(*args, **kwargs)


class FavoriteLot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'lot')
