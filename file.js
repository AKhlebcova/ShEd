    function init() {
    var url_template='{{ tms_url }}1.0/{{ shapefile.id }}/{z}/{x}/{y}.png/';
    var projection = ol.proj.get('EPSG:4326');
    var source = new ol.source.XYZ({
        crossOrigin: 'null',
        wrapX: false,
        projection: projection,
        tileUrlFunction: function(tileCoord) {
            var z = tileCoord[0] - 1;
            var x = tileCoord[1];
            var y = Math.pow(2, z) + tileCoord[2];
            return url_template.replace('{z}', z.toString())
                               .replace('{x}', x.toString())
                               .replace('{y}', y.toString());
                               },
        });

    var layer = new ol.layer.Tile({source: source,
                                   projection: projection,
                                   });


    var view = new ol.View({center: [0, 0],
                            zoom: 1,
                            projection: projection,
                            });

    var map = new ol.Map({target: "map",
                          layers: [layer],
                          view: view});
    map.on ("singleclick", function(e) {
        var request = jQuery.ajax({
            url : "/find_feature",
            data : {id : {{ shapefile.id }},
            latitude : e.coordinate[1],
            longitude : e.coordinate[0]},
            success: function(response) {
                if (response != "") {
                    window.location.href = response
                }
            }
        });
    });
    }
