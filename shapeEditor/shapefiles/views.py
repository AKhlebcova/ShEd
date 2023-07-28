import traceback

from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
from django.urls import reverse_lazy
from shared.models import *
from django.shortcuts import render
from django.contrib.gis.geos import Point
from . import shapefileIO
from .forms import ImportShapefileForm
from shared.utils import calc_search_radius, get_map_form, calc_geometry_field

# def list_shapefiles(request):
#     shapefiles = Shapefile.objects.all().order_by('filename')
#     return render(request, "list_shapefiles.html",
#                   {'shapefiles' : shapefiles})

from django.views.generic import ListView, DetailView, DeleteView


class ShapefilesList(ListView):
    model = Shapefile
    queryset = Shapefile.objects.all().order_by('filename')
    template_name = 'list_shapefiles.html'
    context_object_name = 'shapefiles'
    # paginate_by = 3

class ShapefileDetail(DetailView):
    model = Shapefile
    template_name = 'shape_detail.html'
    context_object_name = 'file'
    pk_url_kwarg = 'id'


def import_shapefile(request):
    if request.method == "GET":
        form = ImportShapefileForm()
        return render(request, "import_shapefile.html",
                      {'form': form,
                       'errMsg': None})
    elif request.method == "POST":
        errMsg = None  # initially.

        form = ImportShapefileForm(request.POST,
                                   request.FILES)
        if form.is_valid():
            shapefile = request.FILES['import_file']
            errMsg = shapefileIO.import_data(shapefile)
            if errMsg == None:
                return HttpResponseRedirect("/")

        return render(request, "import_shapefile.html",
                      {'form': form,
                       'errMsg': errMsg})


def export_shapefile(request, id):
    try:
        shapefile = Shapefile.objects.get(id=id)
        print(shapefile.filename)
    except Shapefile.DoesNotExist:
        raise Http404

    return shapefileIO.export_data(shapefile)


def edit_shapefile(request, id):
    try:
        shapefile = Shapefile.objects.get(id=id)
    except Shapefile.DoesNotExist:
        raise HttpResponseNotFound()

    tms_url = f'http://{request.get_host()}/tms/'

    add_feature_url = f'http://{request.get_host()}/edit_feature/{str(id)}/'

    return render(request, "select_feature.html", {'shapefile': shapefile, 'tms_url': tms_url, 'add_feature_url': add_feature_url})

def find_feature(request):
    try:
        id = int(request.GET['id'])
        latitude = float(request.GET['latitude'])
        longitude = float(request.GET['longitude'])
        shapefile = Shapefile.objects.get(id=id)
        pt = Point(longitude, latitude)
        radius = calc_search_radius(latitude, longitude, 100)
        if shapefile.geom_type == "Point":
            query = Feature.objects.filter(geom_point__dwithin = (pt, radius))
        elif shapefile.geom_type in ["LineString", "MultilineString"]:
            query = Feature.objects.filter(geom_multilinestring__dwithin = (pt, radius))
        elif shapefile.geom_type in ["Polygon", "MultiPolygon"]:
            query = Feature.objects.filter(geom_multipolygon__dwithin = (pt, radius))
        elif shapefile.geom_type == "MultiPoint":
            query = Feature.objects.filter(geom_multipoint__dwithin=(pt, radius))
        elif shapefile.geom_type == "GeometryCollection":
            query = Feature.objects.filter(geom_geometrycollection__dwithin = (pt, radius))
        else:
            print(f"Unsupported geometry: {shapefile.geom_type}")
            return HttpResponse("")
        if query.count() != 1:
            return HttpResponse("")
        feature = query[0]
        return HttpResponse(f"/edit_feature/{str(id)}/{str(feature.pk)}/")
    except:
        traceback.print_exc()
        return HttpResponse("")

def edit_feature(request, id, pk=None):
    if request.method == "POST" and "delete" in request.POST:
        return HttpResponseRedirect(f"/edit_feature/{id}/{pk}/delete_feature/")
    try:
        shapefile = Shapefile.objects.get(id=id)
    except Shapefile.DoesNotExist:
        return HttpResponseNotFound()

    if pk == None:
        feature = Feature.objects.create(shapefile=shapefile)

    else:
        try:
            feature = Feature.objects.get(id=pk)
        except Feature.DoesNotExist:
            return HttpResponseNotFound()

    attributes = []
    for attr_value in feature.attributevalue_set.all():
        attributes.append([attr_value.attribute.name, attr_value.value])
    attributes.sort()
    geometry_field = calc_geometry_field(shapefile.geom_type)
    form_class = get_map_form(shapefile)
    if request.method == "GET":
        wkt = getattr(feature, geometry_field)
        form = form_class({'geometry': wkt})
        return render(request, "edit_feature.html", {'shapefile': shapefile,
                                                     'form': form,
                                                     'attributes': attributes})
    elif request.method == "POST":
        form = form_class(request.POST)
        try:
            if form.is_valid():
                wkt = form.cleaned_data['geometry']
                setattr(feature, geometry_field, wkt)
                feature.save()
                return HttpResponseRedirect(f"/{id}/edit/")
        except ValueError:
            pass
        return render(request, "edit_feature.html", {'shapefile': shapefile,
                                                     'form': form,
                                                     'attributes': attributes})


    # return HttpResponse("Continous")
def delete_feature(request, id, pk):
    try:
        feature = Feature.objects.get(id=pk)
    except Feature.DoesNotExist:
        print('1111')
        return HttpResponseNotFound()
    if request.method == "POST":
        if request.POST['confirm'] == "1":
            feature.delete()
            return HttpResponseRedirect(f"/{id}/edit/")
    return render(request, "delete_feature.html")


class ShapefileDelete(DeleteView):
    model = Shapefile
    template_name = 'delete_shapefile.html'
    pk_url_kwarg = 'id'
    success_url = reverse_lazy('shape_list')





# Create your views here.
