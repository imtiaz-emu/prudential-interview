from django.urls import path
from . import views

app_name = 'gallery'

urlpatterns = [
    path('', views.gallery, name='index'),
    path('image/<int:image_id>/', views.detail, name='detail'),
]
