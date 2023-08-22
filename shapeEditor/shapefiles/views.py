import traceback
from copy import deepcopy
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
from django.urls import reverse_lazy, reverse
from shared.models import *
from django.shortcuts import render, redirect
from django.contrib.gis.geos import Point
from . import shapefileIO
from .forms import ImportShapefileForm, CreateShapefileForm, AttributeFormset
from shared.utils import calc_search_radius, get_map_form, calc_geometry_field, get_attr_form
from osgeo import ogr
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

from django.db import IntegrityError

# def list_shapefiles(request):
#     shapefiles = Shapefile.objects.all().order_by('filename')
#     return render(request, "list_shapefiles.html",
#                   {'shapefiles' : shapefiles})

from django.views.generic import ListView, DetailView, DeleteView, CreateView


class ShapefilesList(ListView):
    model = Shapefile
    queryset = Shapefile.objects.all().order_by('filename')
    template_name = 'list_shapefiles.html'
    context_object_name = 'shapefiles'
    paginate_by = 5


class SearchShapefilesList(ListView):
    model = Shapefile
    queryset = Shapefile.objects.all().order_by('filename')
    template_name = 'search_results.html'
    context_object_name = 'shapefiles'

    def get_queryset(self):
        query = self.request.GET.get("q")
        queryset = super().get_queryset().filter(filename__icontains=query)
        return queryset

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get("q")
        return context



class UserShapefilesList(LoginRequiredMixin, ListView):
    model = Shapefile
    queryset = Shapefile.objects.all().order_by('filename')
    template_name = 'user_list_shapefiles.html'
    context_object_name = 'shapefiles'
    paginate_by = 5

    def get_queryset(self):
        queryset = super().get_queryset().filter(author=self.request.user)
        return queryset



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
            author = None
            if not request.user.is_anonymous:
                author = request.user
            errMsg = shapefileIO.import_data(shapefile, author=author)
            if errMsg == None:

                return HttpResponseRedirect("/")

        return render(request, "import_shapefile.html",
                      {'form': form,
                       'errMsg': errMsg})


def export_shapefile(request, id):
    try:
        shapefile = Shapefile.objects.get(id=id)
        # print(shapefile.filename)
    except Shapefile.DoesNotExist:
        raise Http404

    return shapefileIO.export_data(shapefile)


@login_required
def edit_shapefile(request, id):
    try:
        shapefile = Shapefile.objects.get(id=id)
    except Shapefile.DoesNotExist:
        raise HttpResponseNotFound()
    tms_url = f'http://{request.get_host()}/tms/'

    add_feature_url = f'http://{request.get_host()}/edit_feature/{str(id)}/'

    return render(request, "select_feature.html", {'shapefile': shapefile, 'tms_url': tms_url, 'add_feature_url': add_feature_url})


@login_required
def find_feature(request):
    try:
        id = int(request.GET['id'])
        latitude = float(request.GET['latitude'])
        longitude = float(request.GET['longitude'])
        shapefile = Shapefile.objects.get(id=id)
        if request.user != shapefile.author:
            messages.error(request, f"You can't edit shapefile {shapefile.filename} because you are not the owner, try to add it in your profile.")
            return HttpResponse("")

        pt = Point(longitude, latitude)
        radius = calc_search_radius(latitude, longitude, 100)
        if shapefile.geom_type == "Point":
            query = Feature.objects.filter(geom_point__dwithin=(pt, radius), shapefile_id=shapefile.id)
        elif shapefile.geom_type in ["LineString", "MultilineString"]:
            query = Feature.objects.filter(geom_multilinestring__dwithin=(pt, radius), shapefile_id=shapefile.id)
        elif shapefile.geom_type in ["Polygon", "MultiPolygon"]:
            query = Feature.objects.filter(geom_multipolygon__dwithin=(pt, radius), shapefile_id=shapefile.id)
        elif shapefile.geom_type == "MultiPoint":
            query = Feature.objects.filter(geom_multipoint__dwithin=(pt, radius), shapefile_id=shapefile.id)
        elif shapefile.geom_type == "GeometryCollection":
            query = Feature.objects.filter(geom_geometrycollection__dwithin=(pt, radius), shapefile_id=shapefile.id)
        else:
            print(f"Unsupported geometry: {shapefile.geom_type}")
            return redirect("")
        if query.count() != 1:
            # print(query)
            return HttpResponse("")
        feature = query[0]
        return HttpResponse(f"/edit_feature/{str(shapefile.id)}/{str(feature.pk)}/")
    except:
        traceback.print_exc()
        return HttpResponse("")

@login_required
def edit_feature(request, id, pk=None):
    try:
        shapefile = Shapefile.objects.get(id=id)
    except Shapefile.DoesNotExist:
        return HttpResponseNotFound()
    if request.user != shapefile.author:
         messages.error(request, f"You can't edit shapefile {shapefile.filename} because you are not the owner, try to add it in your profile.")
         return redirect('shape_detail', shapefile.id)

    if request.method == "POST" and "delete" in request.POST:
        return HttpResponseRedirect(f"/edit_feature/{id}/{pk}/delete_feature/")

    if pk == None:
        feature = Feature(shapefile=shapefile)


    else:
        try:
            feature = Feature.objects.get(id=pk)
        except Feature.DoesNotExist:
            return HttpResponseNotFound()

    data = {}
    if pk != None:
        for attr_value in feature.attributevalue_set.all():
            if attr_value.value == None:
                data[attr_value.attribute.name] = None

            elif attr_value.attribute.type == ogr.OFTInteger or attr_value.attribute.type == ogr.OFTInteger64:
                data[attr_value.attribute.name] = int(attr_value.value)
            elif attr_value.attribute.type == ogr.OFTReal:
                data[attr_value.attribute.name] = float(attr_value.value)
            elif attr_value.attribute.type == ogr.OFTDate:
                data[attr_value.attribute.name] = datetime.strptime(attr_value.value, '%Y,%m,%d')
            # elif attr_value.attribute.type == ogr.OFTTime:
            #     data[attr_value.attribute.name] = datetime.strptime(attr_value.value, '%H,%M,%S.%f,%Z')
            # elif attr_value.attribute.type == ogr.OFTDateTime:
            #     data[attr_value.attribute.name] = datetime.strptime(attr_value.value, '%Y,%m,%d,%H,%M,%S.%f,%Z')
            else:
                data[attr_value.attribute.name] = attr_value.value

    # attributes = []
    # for attr_value in feature.attributevalue_set.all():
    #     attributes.append([attr_value.attribute.name, attr_value.value])
    # attributes.sort()
    geometry_field = calc_geometry_field(shapefile.geom_type)
    form_class = get_map_form(shapefile)
    attr_form_class = get_attr_form(shapefile, feature)
    if request.method == "GET":
        wkt = getattr(feature, geometry_field)

        form = form_class({'geometry': wkt})
        attr_form = attr_form_class(data)
        return render(request, "edit_feature.html", {'shapefile': shapefile,
                                                     'form': form,
                                                     # 'attributes': attributes,
                                                     'attr_form': attr_form})
    elif request.method == "POST":
        form = form_class(request.POST)
        attr_form = attr_form_class(request.POST, initial=data)
        try:
            if form.is_valid():
                wkt = form.cleaned_data['geometry']

                setattr(feature, geometry_field, wkt)
                feature.save()

            if attr_form.has_changed():
                if attr_form.is_valid():
                    success, result = attr_form.save()

                    if not success:
                        messages.error(request, result)
                        return redirect('edit_feature', id, pk)
                    else:
                        messages.success(request, result)
                return HttpResponseRedirect(f"/{id}/edit/")
        except ValueError:
            pass


        return render(request, "edit_feature.html", {'shapefile': shapefile,
                                                     'form': form,
                                                     # 'attributes': attributes,
                                                     'attr_form': attr_form})


    # return HttpResponse("Continous")

def delete_feature(request, id, pk):
    try:
        feature = Feature.objects.get(id=pk)
    except Feature.DoesNotExist:
        # print('1111')
        return HttpResponseNotFound()
    if request.method == "POST":
        # print(request.POST['confirm'])
        if request.POST['confirm'] == "1":
            feature.delete()
        return HttpResponseRedirect(f"/{id}/edit/")

    return render(request, "delete_feature.html")


class ShapefileDelete(LoginRequiredMixin, DeleteView):
    model = Shapefile
    template_name = 'delete_shapefile.html'
    pk_url_kwarg = 'id'
    success_url = reverse_lazy('shape_list')



# class ShapefileCreate(CreateView):
#     form_class = CreateShapefileForm
#     model = Shapefile
#     template_name = 'create_shapefile.html'
#     # pk_url_kwarg = 'id'
#     success_url = reverse_lazy('shape_list')

    # def form_valid(self, form):
    #     return super().form_valid(form)

def create_shapefile(request):
    if request.method == "GET":
        form = CreateShapefileForm()
        formset = AttributeFormset(request.GET or None)
        return render(request, "create_shapefile.html", {'form': form,
                                                         'formset': formset})
    elif request.method == "POST":
        # print(request.POST)
        form = CreateShapefileForm(request.POST)
        formset = AttributeFormset(request.POST)
        if form.is_valid() and formset.is_valid():
            # print('!!!')
            success, new_shape, message = form.save(request.user)
            if not success:
                messages.error(request, message)
                return render(request, "create_shapefile.html", {'form': form,
                                                                 'formset': formset})
            for f in formset:
                name = f.cleaned_data.get('name')
                type = int(f.cleaned_data.get('type'))
                width = f.cleaned_data.get('width')
                precision = 0
                if type == 2:
                    precision = f.cleaned_data.get('precision')
                    if precision is None:
                        precision = 0
                attr = Attribute(shapefile=new_shape,
                                 name=name,
                                 type=type,
                                 width=width,
                                 precision=precision,
                                 )
                attr.save()
                # try:
                #     attr.save()
                # except IntegrityError:
                #     new_shape.delete()
                #     message = "Duplicate field name"
                #     print(message)
                #     messages.error(request, message)
                #     return render(request, "create_shapefile.html", {'form': form,
                #                                                      'formset': formset})
            return redirect('shape_list')

        else:
            return render(request, "create_shapefile.html", {'form': form,
                                                             'formset': formset})


# def add_attributes(request):
#     template_name = 'add_attr.html'
#     heading_message = 'Formset Demo'
#     if request.method == 'GET':
#         formset = AttributeFormset(request.GET or None)
#     elif request.method == 'POST':
#         print(request.POST)
#         formset = AttributeFormset(request.POST)
#         if formset.is_valid():
#             for form in formset:
#                 name = form.cleaned_data.get('name')
#                 type = form.cleaned_data.get('type')
#                 width = form.cleaned_data.get('width')
#                 if name:
#                     sh = Shapefile.objects.get(id=29)
#                     attr = Attribute(shapefile=sh,
#                                      name=name,
#                                      type=type,
#                                      width=width,
#                                      precision=0,
#                                      )
#                     attr.save()
#             return redirect('shape_list')
#     return render(request, template_name, {
#         'formset': formset,
#         'heading': heading_message,
#     })



# Create your views here.
@login_required
def add_to_profile(request, id):
    new_sh = Shapefile.objects.get(id=id)
    new_sh.pk = None
    new_sh.author = request.user
    new_sh.save()
    qs_attr = Attribute.objects.filter(shapefile=id)
    qs_feature = Feature.objects.filter(shapefile=id)
    qs_value = AttributeValue.objects.filter(feature__in=qs_feature, attribute__in=qs_attr)
    attr_keys = {}
    for attr in qs_attr:
        key = attr.id
        attr.pk = None
        attr.shapefile = new_sh
        attr.save()
        attr_keys[key] = attr

    feature_keys = {}
    for feature in qs_feature:
        key = feature.id
        feature.pk = None
        feature.shapefile = new_sh
        feature.save()
        feature_keys[key] = feature
    for obj in qs_value:
        attr_key = obj.attribute.id
        feature_key = obj.feature.id
        value = obj.value
        AttributeValue.objects.create(
            feature=feature_keys[feature_key],
            attribute=attr_keys[attr_key],
            value=value
        )

    return redirect('shape_detail', new_sh.id)


