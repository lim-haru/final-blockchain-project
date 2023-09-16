from django.urls import path
from allauth.account.views import LoginView, SignupView
from . import views


urlpatterns = [
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('signup/', SignupView.as_view(template_name='signup.html'), name='signup'),
    path('logout/', views.custom_logout, name='custom_logout'),

    path('', views.home, name='home'),

    path('collections', views.lots, name='collections'),
    path('collections/<int:pk>/', views.lot, name='collection'),

    path('purchased', views.purchased, name='purchased'),
    path('activity', views.activity, name='activity'),
    path('saved', views.saved, name='saved'),
    
    path('submit_bid/<int:pk>/', views.SubmitBidView.as_view(), name='submit_bid'),
    path('add_to_favorites/<int:lot_id>/', views.add_to_favorites, name='add_to_favorites'),
    path('remove_from_favorites/<int:lot_id>/', views.remove_from_favorites, name='remove_from_favorites'),
]
