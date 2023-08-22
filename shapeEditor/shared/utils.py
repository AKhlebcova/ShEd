from django.contrib.gis.geos.collections import MultiPolygon, MultiLineString, MultiPoint
from osgeo import ogr
import pyproj
# from django.contrib.gis import forms
import floppyforms as forms
from shared.models import Attribute, AttributeValue

from datetime import datetime
def wrap_geos_geometry(geometry):
    if geometry.geom_type == "Polygon":
        return MultiPolygon(geometry)
    elif geometry.geom_type == "LineString":
        return MultiLineString(geometry)
    elif geometry.geom_type == "Point":
        return MultiPoint(geometry)
    else:
        return geometry


def calc_geometry_field(geometry_type):
    if geometry_type == "Polygon":
        return "geom_multipolygon"
    elif geometry_type == "LineString":
        return "geom_multilinestring"
    elif geometry_type == "Point":
        return "geom_multipoint"
    else:
        return "geom_" + geometry_type.lower()


def get_ogr_feature_attribute(attr, feature):
    attr_name = attr.name

    if not feature.IsFieldSet(attr_name):
        return (True, None)

    if attr.type == ogr.OFTInteger:
        value = str(feature.GetFieldAsInteger(attr_name))
    elif attr.type == ogr.OFTInteger64:
        value = str(feature.GetFieldAsInteger64(attr_name))
    elif attr.type == ogr.OFTIntegerList:
        value = repr(feature.GetFieldAsIntegerList(attr_name))
    elif attr.type == ogr.OFTReal:
        value = feature.GetFieldAsDouble(attr_name)
        value = "%*.*f" % (attr.width, attr.precision, value)
    elif attr.type == ogr.OFTRealList:
        values = feature.GetFieldAsDoubleList(attr_name)
        str_values = []
        for value in values:
            str_values.append("%*.*f" % (attr.width,
                                         attr.precision, value))
        value = repr(str_values)
    elif attr.type == ogr.OFTString:
        value = feature.GetFieldAsString(attr_name)
    elif attr.type == ogr.OFTStringList:
        value = repr(feature.GetFieldAsStringList(attr_name))
    elif attr.type == ogr.OFTDate:
        parts = feature.GetFieldAsDateTime(attr_name)
        year, month, day, hour, minute, second, tzone = parts
        value = "%d,%d,%d" % (year, month, day)
    elif attr.type == ogr.OFTTime:
        parts = feature.GetFieldAsDateTime(attr_name)
        year, month, day, hour, minute, second, tzone = parts
        value = "%d,%d,%d,%d" % (hour, minute, second, tzone)
    elif attr.type == ogr.OFTDateTime:
        parts = feature.GetFieldAsDateTime(attr_name)
        year, month, day, hour, minute, second, tzone = parts
        value = "%d,%d,%d,%d,%d,%d,%d,%d" % (year, month, day, hour, minute, second, tzone)
    else:
        return (False, "Unsupported attribute type: " +
                str(attr.type) + attr_name)

    return (True, value)



def unwrap_geos_geometry(geometry):
    try:
        geometry.geom_type
        if geometry.geom_type in ["MultiPolygon",
                                  "MultiLineString",
                                  "MultiPoint"]:
            if len(geometry) == 1:
                geometry = geometry[0]
        return geometry
    except AttributeError:
        pass




def set_ogr_feature_attribute(attr, value, feature):
    attr_name = attr.name

    if value == None:
        feature.UnsetField(attr_name)
        return

    if attr.type == ogr.OFTInteger:
        feature.SetField(attr_name, int(value))
    elif attr.type == ogr.OFTInteger64:
        feature.SetField(attr_name, int(value))
    elif attr.type == ogr.OFTIntegerList:
        integers = eval(value)
        feature.SetFieldIntegerList(attr_name, integers)
    elif attr.type == ogr.OFTReal:
        feature.SetField(attr_name, float(value))
    elif attr.type == ogr.OFTRealList:
        floats = []
        for s in eval(value):
            floats.append(eval(s))
        feature.SetFieldDoubleList(attr_name, floats)
    elif attr.type == ogr.OFTString:
        feature.SetField(attr_name, value)
    elif attr.type == ogr.OFTStringList:
        strings = []
        for s in eval(value):
            strings.append(s.encode())
        feature.SetFieldStringList(attr_name, strings)
    elif attr.type == ogr.OFTDate:
        parts = value.split(",")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        # tzone = int(parts[3])
        feature.SetField(attr_name, year, month, day,
                         0, 0, 0, 0)
    elif attr.type == ogr.OFTTime:
        parts = value.split(",")
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2])
        tzone = int(parts[3])
        feature.SetField(attr_name, 0, 0, 0,
                         hour, minute, second, tzone)
    elif attr.type == ogr.OFTDateTime:
        parts = value.split(",")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3])
        minute = int(parts[4])
        second = int(parts[5])
        tzone = int(parts[6])
        feature.SetField(attr_name, year, month, day,
                         hour, minute, second, tzone)

def calc_search_radius(latitude, longitude, distance):
    geod = pyproj.Geod(ellps="WGS84")
    x, y, angle = geod.fwd(longitude, latitude, 0, distance)
    radius = y - latitude
    x, y, angle = geod.fwd(longitude, latitude, 90, distance)
    radius = max(radius, x - longitude)
    x, y, angle = geod.fwd(longitude, latitude, 180, distance)
    radius = max(radius, latitude - y)

    x, y, angle = geod.fwd(longitude, latitude, 270, distance)
    radius = max(radius, longitude - x)
    return radius

def get_attr_form(shapefile, feature):
    attributes = Attribute.objects.filter(shapefile=shapefile)
    # fields = {}
    # for attr in attributes:
    #     fields[attr.name] = (attr.type, attr.width, attr.precision
    #     fields.append(attr.name)

    class ShapefileAtributeForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for attr in attributes:
                field_name = '%s' % (attr.name,)
                if attr.type == ogr.OFTInteger or attr.type == ogr.OFTInteger64:
                    self.fields[field_name] = forms.IntegerField(max_value=10**attr.width - 1, required=False)
                elif attr.type == ogr.OFTReal:
                    self.fields[field_name] = forms.DecimalField(decimal_places=attr.precision, required=False)
                elif attr.type == ogr.OFTDate:
                    self.fields[field_name] = forms.DateField(required=False, help_text='Input date')
                # elif attr.type == ogr.OFTTime:
                #     self.fields[field_name] = forms.TimeField(required=False, help_text='Input time')
                # elif attr.type == ogr.OFTDateTime:
                #     self.fields[field_name] = forms.TimeField(required=False, help_text='Input date and time')
                # elif attr.type == ogr.OFTString:
                #     self.fields[field_name] = forms.CharField(max_length=attr.width, required=False)
                # elif attr.type == ogr.OFTIntegerList or attr.type == ogr.OFTRealList or attr.type == ogr.OFTStringList:
                #     self.fields[field_name] = forms.CharField(max_length=attr.width, required=False, widget=forms.Textarea)
                else:
                    self.fields[field_name] = forms.CharField(max_length=attr.width, required=False)


        def save(self):
            for attr in self.changed_data:
                attr_obj = Attribute.objects.get(name=attr, shapefile=shapefile)

                try:
                    if self.cleaned_data.get(attr) == None:
                        value = None
                    elif attr_obj.type == ogr.OFTInteger or attr_obj.type == ogr.OFTInteger64:
                        int(self.cleaned_data.get(attr))
                        value = str(self.cleaned_data.get(attr))
                    elif attr_obj.type == ogr.OFTReal:
                        float(self.cleaned_data.get(attr))
                        value = str(round(self.cleaned_data.get(attr), attr_obj.precision))
                    elif attr_obj.type == ogr.OFTDate:
                        value = (self.cleaned_data.get(attr)).strftime('%Y,%m,%d')
                    else:
                        value = self.cleaned_data.get(attr)

                    attr_val, created = AttributeValue.objects.get_or_create(attribute=attr_obj, feature=feature)
                    attr_val.value = value
                    attr_val.save()
                except TypeError:
                    return (False, f"Error of attribute type: {str(attr_obj.type)} {attr_obj.name}")
                except ValueError:
                    return (False, f"Error of attribute value: {str(attr_obj.type)} {attr_obj.name}")

            return (True, "Success changes")


    return ShapefileAtributeForm






def get_map_form(shapefile):
    geometry_field = calc_geometry_field(shapefile.geom_type)
    if geometry_field == "geom_multipoint":
        field = forms.gis.MultiPointField
        widget_class = forms.gis.MultiPointWidget
    elif geometry_field == "geom_multilinestring":
        field = forms.gis.MultiLineStringField
        widget_class = forms.gis.MultiLineStringWidget
    elif geometry_field == "geom_multipolygon":
        field = forms.gis.MultiPolygonField
        widget_class = forms.gis.MultiPolygonWidget
    elif geometry_field == "geom_geometrycollection":
        field = forms.gis.GeometryCollectionField
        widget_class = forms.gis.GeometryCollectionWidget
    else:
        raise RuntimeError(f"Unsupported field: {geometry_field}")


    class MapWidget(forms.gis.BaseOsmWidget, widget_class):
        map_width = 1000
        map_height = 700
        pass
    widget = MapWidget()

    class MapForm(forms.Form):
        geometry = field(widget=MapWidget, required=True)

    return MapForm


