from django.urls import path
from .views import *

urlpatterns = [
    # path('', list_shapefiles, name='start_page'),
    path('', ShapefilesList.as_view(), name='shape_list'),
    path('find_feature/', find_feature, name='find'),
    path('import/', import_shapefile, name='shape_import'),
    path('<int:id>/export/', export_shapefile, name='shape_export'),
    path('<int:id>/edit/', edit_shapefile, name='shape_edit'),
    path('edit_feature/<int:id>/<int:pk>/', edit_feature, name='edit_feature'),
    path('<int:id>/', ShapefileDetail.as_view(), name='shape_detail'),
]