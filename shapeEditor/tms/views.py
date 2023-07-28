import mapnik
from django.http import HttpResponse, Http404
import traceback
import os
from django.shortcuts import render
from shared.models import Shapefile
from django.template.response import TemplateResponse
import math
from shapeEditor.settings import DATABASES, BASE_DIR
from shared.utils import calc_geometry_field

ROOT = os.path.dirname(__file__)

MAX_ZOOM_LEVEL = 10
TILE_WIDTH = 256
TILE_HEIGHT = 256


def root(request):
    try:
        baseURL = request.build_absolute_uri()
        # xml = os.path.join(ROOT, 'root.xml')
        xml = 'root.xml'
        # response = ''
        # with open(xml, "r") as f:
        #     for line in f:
        #         response += line
        return TemplateResponse(request, xml, content_type="text/xml", context={"baseURL": baseURL})

        # return HttpResponse(xml, content_type="text/xml")
    except:
        traceback.print_exc()
    return HttpResponse("Ошибка")


def service(request, version):
    try:
        if version != "1.0":
            raise Http404
        baseURL = request.build_absolute_uri()
        xml = 'service.xml'
        data = {}
        for shapefile in Shapefile.objects.all():
            id = str(shapefile.id)
            data[id] = shapefile.filename

        return TemplateResponse(request, xml, content_type="text/xml", context={"baseURL": baseURL, 'data': data})

        # return HttpResponse(xml, content_type="text/xml")
    except:
        traceback.print_exc()
    return HttpResponse("Ошибка")

    # return HttpResponse("Служба сборных цифровых карт")


def _unitsPerPixel(zoomLevel):
    return 0.703125 / math.pow(2, zoomLevel)


def tileMap(request, version, id):
    if version != "1.0":
        raise Http404
    try:
        shapefile = Shapefile.objects.get(id=id)
    except Shapefile.DoesNotExist:
        raise Http404
    try:
        baseURL = request.build_absolute_uri()
        xml = 'tilemap.xml'
        data = {}

        for zoomLevel in range(0, MAX_ZOOM_LEVEL + 1):
            href = f"{baseURL}{zoomLevel}/"
            unitsperpixel = f"{_unitsPerPixel(zoomLevel)}"
            order = f"{zoomLevel}"
            data[order] = (href, unitsperpixel)

        return TemplateResponse(request, xml, content_type="text/xml", context={
            "baseURL": baseURL,
            'shapefile': shapefile,
            'TILE_WIDTH': TILE_WIDTH,
            'TILE_HEIGHT': TILE_HEIGHT,
            'data': data})
    except:
        traceback.print_exc()
    return HttpResponse("Ошибка")

    # return HttpResponse("Сборная карта")


def tile(request, version, id, zoom, x, y):
    try:
        if version != "1.0":
            raise Http404
        try:
            shapefile = Shapefile.objects.get(id=id)
        except Shapefile.DoesNotExist:
            raise Http404
        zoom = int(zoom)
        x = int(x)
        y = int(y)
        if zoom < 0 or zoom > MAX_ZOOM_LEVEL:
            raise Http404
        xExtent = _unitsPerPixel(zoom) * TILE_WIDTH
        yExtent = _unitsPerPixel(zoom) * TILE_HEIGHT
        minlong = x * xExtent - 180.0
        minlat = y * yExtent - 90.0
        maxlong = minlong + xExtent
        maxlat = minlat + yExtent
        if (minlong < -180 or maxlong > 180 or minlat < -90 or maxlat > 90):
            raise Http404

        map = os.path.join(BASE_DIR, 'templates/map_create.xml')
        map_string = ''
        with open(map, "r") as f:
            for line in f:
                map_string += line


        dbSettings = DATABASES['default']
        user = dbSettings['USER']
        passwd = dbSettings['PASSWORD']
        dbname = dbSettings['NAME']
        geometry_field = calc_geometry_field(shapefile.geom_type)

        query = f'''(select {geometry_field} from "shared_feature" where shapefile_id={str(shapefile.id)}) as geom'''
        symbolizer = ""
        if shapefile.geom_type in ["Point", "MultiPoint"]:
            symbolizer = '<PointSymbolizer />'
        elif shapefile.geom_type in ["LineString", "MultilineString"]:
            symbolizer = '<LineSymbolizer stroke="#94590c" stroke-width="1" />'
        elif shapefile.geom_type in ["Polygon", "MultiPolygon"]:
            symbolizer = '''<PolygonSymbolizer fill="#79940c"/>
            <LineSymbolizer stroke="#94590c" stroke-width="1"/>'''
        map_string = map_string.replace("<!--(Symbolizers)-->", symbolizer)
        map_string = map_string.replace("(Database)", dbname)
        map_string = map_string.replace("(DatabaseUser)", user)
        map_string = map_string.replace("(UserPassword)", passwd)
        map_string = map_string.replace("(Query)", query)
        map_string = map_string.replace("(GeometryField)", geometry_field)

        gmap = mapnik.Map(TILE_WIDTH, TILE_HEIGHT)
        mapnik.load_map_from_string(gmap, map_string)

        bbox = mapnik.Box2d(minlong, minlat, maxlong, maxlat)
        gmap.zoom_to_box(bbox)

        image = mapnik.Image(TILE_WIDTH, TILE_HEIGHT)
        mapnik.render(gmap, image)
        image_Data = image.tostring('png')
        return HttpResponse(image_Data, content_type="image/png")
    except:
        traceback.print_exc()
    return HttpResponse("Ошибка")

    # return HttpResponse("Сегмент сборной карты")
