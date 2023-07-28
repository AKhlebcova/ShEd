from django.urls import path, register_converter
from .views import *
from . import converters

register_converter(converters.VersionConverter, 'ver')


urlpatterns = [
    path('', root, name='tms'),
    path('<ver:version>/', service, name='tl_service'),
    path('<ver:version>/<int:id>/', tileMap, name='t_map'),
    path('<ver:version>/<int:id>/<int:zoom>/<int:x>/<int:y>.png/', tile, name='tile'),
]



