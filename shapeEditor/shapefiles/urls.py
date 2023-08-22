from django.urls import path
from .views import *

urlpatterns = [
    # path('', list_shapefiles, name='start_page'),
    path('', ShapefilesList.as_view(), name='shape_list'),
    path('profile/', UserShapefilesList.as_view(), name='my_shape_list'),
    path('search/', SearchShapefilesList.as_view(), name='search_results'),
    path('find_feature/', find_feature, name='find'),
    path('import/', import_shapefile, name='shape_import'),
    path('<int:id>/export/', export_shapefile, name='shape_export'),
    path('<int:id>/edit/', edit_shapefile, name='shape_edit'),
    path('<int:id>/delete/', ShapefileDelete.as_view(), name='shape_del'),
    path('<int:id>/add/', add_to_profile, name='shape_add_to_profile'),


    path('edit_feature/<int:id>/<int:pk>/', edit_feature, name='edit_feature'),
    path('edit_feature/<int:id>/', edit_feature, name='add_feature'),
    path('<int:id>/', ShapefileDetail.as_view(), name='shape_detail'),
    path('edit_feature/<int:id>/<int:pk>/delete_feature/', delete_feature, name='delete_feature'),
    path('create/', create_shapefile, name='shape_create'),
    # path('add_attributes/', add_attributes, name='add_attr'),



]