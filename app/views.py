from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from .models import Lot, FavoriteLot
from django.views import View
from django.http import HttpResponseRedirect
import redis, os
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy


redis_client = redis.Redis.from_url(os.environ.get('REDIS_LOCATION'))

def lots_info(category_filter):
    current_time = timezone.now()

    if category_filter == 'all' or category_filter is None:
        open_lots = Lot.objects.filter(status='open').order_by('endAuction').values()
        closed_lots = Lot.objects.filter(status='closed').order_by('-endAuction').values()
    else:
        open_lots = Lot.objects.filter(status='open', category=category_filter).order_by('endAuction').values()
        closed_lots = Lot.objects.filter(status='closed', category=category_filter).order_by('-endAuction').values()

    current_prices = {}
    times_left = {}
    starts_auction = {} 
    initial_prices = {}

    for lot in open_lots:
        try:
            current_prices[lot['id']] = get_highest_bid_from_redis(f"lot:{lot['id']}:bids")[1]
        except:
            pass

        # verifica se l'asta è già iniziata
        if current_time > lot['startAuction']:
            # calcolo tempo rimanente dell'asta
            try:                                           
                endAuction_str = redis_client.get(f"lot:{lot['id']}:endAuction")
                endAuction = datetime.strptime(endAuction_str.decode('ascii'), '%Y-%m-%d %H:%M:%S.%f%z')
                times_left[lot['id']] = str(endAuction - current_time).split('.')[0]
            except:
                times_left[lot['id']] = 0
        else:
            starts_auction[lot['id']] = lot['startAuction']
            initial_prices[lot['id']] = lot['startingPrice']

    upcoming_lots = open_lots.filter(startAuction__gte=current_time)
    open_lots = open_lots.filter(startAuction__lt=current_time)

    selling_prices = {}
    winners = {}
    for lot in closed_lots:
        selling_prices[lot['id']] = lot['price']
        winners[lot['id']] = lot['winner']
    
    return open_lots, closed_lots, current_prices, times_left, starts_auction, initial_prices, selling_prices, winners, upcoming_lots



def custom_logout(request):
    logout(request)

    return redirect(home)



def home(request):
    current_time = timezone.now()

    open_lots = Lot.objects.filter(status='open', startAuction__lt=current_time).order_by('endAuction').values()[:4]
    nLots = Lot.objects.count()
    nOpenLots = Lot.objects.filter(status='open').count()
    try:
        nBids = int(redis_client.get('number_bids').decode('utf-8'))
    except:
        nBids = 0

    highestBids = []
    current_prices = {}
    times_left = {}

    # Ottengo le offerte più alte per ogni lotto
    for n in range(nLots + 1):
        try:
            redis_client.get(f"lot:{n}:bids")
        except:
            if get_highest_bid_from_redis(f"lot:{n}:bids")[0] != 'admin':
                highestBids.append(get_highest_bid_from_redis(f"lot:{n}:bids"))

    # Prezzo attuale
    for lot in open_lots:
        try:
            current_prices[lot['id']] = get_highest_bid_from_redis(f"lot:{lot['id']}:bids")[1]
        except:
            pass

        # verifica se l'asta è già iniziata
        if current_time > lot['startAuction']:
            # calcolo tempo rimanente dell'asta
            try:                                        
                endAuction_str = redis_client.get(f"lot:{lot['id']}:endAuction")
                endAuction = datetime.strptime(endAuction_str.decode('ascii'), '%Y-%m-%d %H:%M:%S.%f%z')
                times_left[lot['id']] = str(endAuction - current_time).split('.')[0]
            except:
                times_left[lot['id']] = 0

    context = {
        'open_lots': open_lots,
        'n_lots': nLots,
        'n_openLots': nOpenLots,
        'n_bids': nBids,
        'highest_bids': highestBids,
        'current_price': current_prices,
        'time_left': times_left,
    }
    return render(request, 'home.html', context)


def lots(request):
    category_filter = request.GET.get('category')

    open_lots, closed_lots, current_prices, times_left, starts_auction, initial_prices, selling_prices, winners, upcoming_lots = lots_info(category_filter)
    
    if request.method == "GET":
        search = request.GET.get('search')
        if search:
            open_lots = open_lots.filter(name=search).values()
            closed_lots = closed_lots.filter(name=search).values()
            upcoming_lots = upcoming_lots.filter(name=search).values()

    context = {
        'open_lots': open_lots,
        'closed_lots': closed_lots,
        'current_price': current_prices,
        'time_left': times_left,
        'start_auction': starts_auction,
        'initial_price':   initial_prices,
        'selling_price': selling_prices,
        'winner': winners,
        'upcoming_lots': upcoming_lots,
    }
    return render(request, 'collections.html', context)


@login_required(login_url=reverse_lazy('login'))
def purchased(request):
    category_filter = request.GET.get('category')

    if category_filter == 'all' or category_filter is None:
        user_lots = Lot.objects.filter(winner=request.user).order_by('-endAuction').values()
    else:
        user_lots = Lot.objects.filter(winner=request.user, category=category_filter).order_by('-endAuction').values()

    return render(request, 'purchased.html', {'user_lots': user_lots})


@login_required(login_url=reverse_lazy('login'))
def lot(request, pk):
    lot = Lot.objects.get(pk=pk)
    offers = get_all_bids_from_redis(f"lot:{pk}:bids")

    current_time = timezone.now()
    if lot.status == 'closed':
        auction_status = 'closed'
    elif current_time > lot.startAuction:
        auction_status = 'started'
    else:
        auction_status = 'upcoming'

    if FavoriteLot.objects.filter(user=request.user, lot=pk).exists():
        lot_saved = True
    else:
        lot_saved = False

    context = {
        'lot': lot,
        'offers': offers,
        'auction_status': auction_status,
        'lot_saved': lot_saved,
    }
    return render(request, 'item.html', context)


@login_required(login_url=reverse_lazy('login'))
def activity(request):
    my_bids = []
    nLots = Lot.objects.count()
    
    # Filtro le aste per ottenere le mie offerte
    for n in range(nLots + 1):
        bids = get_all_bids_from_redis(f"lot:{nLots}:bids")
        for bid in bids:
            if bid[0] == str(request.user):
                my_bids.append((bid, Lot.objects.get(pk=nLots), get_highest_bid_from_redis(f"lot:{nLots}:bids")))
        nLots -= 1
        
    return render(request, 'activity.html', {'my_bids': my_bids})


@login_required(login_url=reverse_lazy('login'))
def saved(request):
    category_filter = request.GET.get('category')

    open_lots, closed_lots, current_prices, times_left, starts_auction, initial_prices, selling_prices, winners, upcoming_lots = lots_info(category_filter)
    
    open_lots = []
    closed_lots = []
    upcoming_lots = []

    saved_lots = FavoriteLot.objects.filter(user=request.user)
    for saved in saved_lots:
        if saved.lot.status == 'open' and timezone.now() > saved.lot.startAuction:
            open_lots.append(saved.lot)
        elif saved.lot.status == 'closed':
            closed_lots.append(saved.lot)
        else:
            upcoming_lots.append(saved.lot)

    context = {
        'open_lots': open_lots,
        'closed_lots': closed_lots,
        'current_price': current_prices,
        'time_left': times_left,
        'start_auction': starts_auction,
        'initial_price':   initial_prices,
        'selling_price': selling_prices,
        'winner': winners,
        'upcoming_lots': upcoming_lots,
    }
    return render(request, 'saved.html', context)

@login_required(login_url=reverse_lazy('login'))
def add_to_favorites(request, lot_id):
    lot = Lot.objects.get(id=lot_id)
    favorite, created = FavoriteLot.objects.get_or_create(user=request.user, lot=lot)
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required(login_url=reverse_lazy('login'))
def remove_from_favorites(request, lot_id):
    lot = Lot.objects.get(id=lot_id)
    favorite = FavoriteLot.objects.filter(user=request.user, lot=lot)
    if favorite.exists():
        favorite.delete()
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))



def get_all_bids_from_redis(bid_key):
    bids = redis_client.lrange(bid_key, 0, -1)
    bids_list = []
    for bid in bids:
        user, bid_amount, date = bid.decode('utf-8').split('|')
        bids_list.append((user, bid_amount, datetime.strptime(date, '%Y-%m-%d %H:%M:%S.%f%z')))

    return bids_list

def get_highest_bid_from_redis(bid_key):
    bids = redis_client.lrange(bid_key, 0, -1)
    highest_bid = 0.0
    for bid in bids:
        user, bid_amount, date = bid.decode('utf-8').split('|')
        bid_amount = float(bid_amount)
        if bid_amount >= highest_bid:
            highest_bid = bid_amount
            highest_bidder = user
            highest_date = date

    return  highest_bidder, highest_bid, datetime.strptime(highest_date, '%Y-%m-%d %H:%M:%S.%f%z')

class SubmitBidView(View):
    def post(self, request, pk, *args, **kwargs):
        if timezone.now() > Lot.objects.get(pk=pk).startAuction:
            bid_amount = request.POST.get('bid_amount')

            bid_key = f"lot:{pk}:bids"

            try:
                highest_bid = get_highest_bid_from_redis(bid_key)[1]
            except:
                highest_bid = 0

            # Se ha un valore ed è maggiore dell'offerta più alta
            if bid_amount and float(bid_amount) > highest_bid:
                bid_data = f"{request.user.username}|{bid_amount}|{timezone.now()}"
                redis_client.lpush(bid_key, bid_data)

                # Incrementa numero totale di offerte fatte
                redis_client.incr('number_bids')
        else:
            messages.error(request, "L'asta non è ancora iniziata")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))