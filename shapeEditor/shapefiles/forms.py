from django import forms
from django.core.exceptions import ValidationError
from shared.models import AttributeValue, Shapefile, Attribute

from django.db import connections
from django.forms import formset_factory, BaseFormSet


class ImportShapefileForm(forms.Form):
    import_file = forms.FileField(label="Select the compressed shapefile")



auth_name = {
    ('EPSG', "EPSG"),
    ('ESRI', "ESRI"),
}

geometry_type = {
    ("Point", "Point"),
    ("MultiPoint", "MultiPoint"),
    ('LineString', "LineString"),
    ('MultilineString', "MultilineString"),
    ('Polygon', "Polygon"),
    ('MultiPolygon', "MultiPolygon"),
}


class CreateShapefileForm(forms.ModelForm):
    filename = forms.CharField(min_length=6, max_length=255, help_text='Enter name of your file',
                            label="Filename")
    auth_name = forms.ChoiceField(choices=auth_name, help_text='Select Author of ID of the Spatial Reference System',
                            label="Organization")
    auth_srid = forms.IntegerField(min_value=2000, max_value=104992,
                                   help_text="Uniquely identifies the Spatial Referencing System (SRS)",
                                   label="SRID ID")
    geom_type = forms.ChoiceField(choices=geometry_type, help_text='Select the type of your geometry',
                                  label="Geometry type")

    class Meta:
        model = Shapefile
        fields = [
            'filename',
            'auth_name',
            'auth_srid',
            'geom_type',
        ]

    def save(self, user, commit=True):
        new_shapefile = None


        srid = self.cleaned_data.get('auth_srid')
        auth_name = self.cleaned_data.get('auth_name')
        query = f'''
                    SELECT srtext FROM spatial_ref_sys WHERE auth_name=\'{auth_name}\' and auth_srid={srid} 
                    '''
        with connections['default'].cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
            if row is None:
                return (False, new_shapefile, "Unknown Spatial Referencing System.")
            else:
                srtext = row[0]
                if not user.is_anonymous:
                    new_shapefile = Shapefile(filename=(self.cleaned_data.get('filename')+".shp"),
                                              srs_wkt=srtext,
                                              geom_type=self.cleaned_data.get('geom_type'),
                                              author=user)
                else:
                    new_shapefile = Shapefile(filename=(self.cleaned_data.get('filename') + ".shp"),
                                              srs_wkt=srtext,
                                              geom_type=self.cleaned_data.get('geom_type'))
                new_shapefile.save()
                return (True, new_shapefile, "Success")




types = {
    (0, "OFTInteger"),
    (12, "OFTInteger64"),
    (2, "OFTReal"),
    (4, "OFTString"),
    (9, "OFTDate"),
}

class AttributeForm(forms.ModelForm):
    name = forms.CharField(
        min_length=3,
        max_length=8,
        label='Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter attribute Name'
        })
    )
    type = forms.ChoiceField(
        label='Attribute type',
        choices=types
        )
    width = forms.IntegerField(label='Cell size', help_text="Number of symbols per cell")
    precision = forms.IntegerField(label='Decimal places', help_text="Only for decimals", required=False)
    class Meta:
        model = Attribute
        fields = [
            'name',
            'type',
            'width',
            'precision',
        ]

    def clean(self):
        super().clean()
        type = int(self.cleaned_data.get('type'))
        width = self.cleaned_data.get('width')
        if type == 9:
            if width < 10:
                self._errors['width'] = self.error_class(
                    ['Error in Cell size - minimum 10 characters for type OFTDate'])
        if type == 2:

            precision = self.cleaned_data.get('precision')
            if precision is None:
                precision = 0
            if (width - precision) < 2:
                self._errors['width'] = self.error_class(['Error in Cell size and Decimal places - minimum 2 more characters, than in Decimal places'])
                # raise ValidationError("Error in Cell size and Decimal places - minimum 2 more characters, than in Decimal places")
        return self.cleaned_data
class AttributeBaseFormset(BaseFormSet):
    def clean(self):

        if any(self.errors):
            return
        names = []

        for num, form in enumerate(self.forms):
            if self.can_delete and self._should_delete_form(form):
                continue
            name = form.cleaned_data.get('name')
            if name in names:
                self.errors[num]['name'] = [f'Duplicate field name in attribute {num+1}']

                raise ValidationError(f'Duplicate field name in attribute {num+1}')
            names.append(name)

        return self.cleaned_data



AttributeFormset = formset_factory(AttributeForm, extra=0, formset=AttributeBaseFormset)






