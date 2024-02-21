import json 
import fiona
import shapely
from shapely.geometry import shape
from frappe import _

def parse_shapefile(file_path):
    """
    Parse contents of shapefile

    Args:
        file_path (str): File path of .shp file
    See https://mapscaping.com/how-to-read-a-shapefile-using-python/
    """
    schema, features = None, []
    parent_geojson = { "type": "FeatureCollection",
                "features": []
             }
    # open the shapefile
    with fiona.open(file_path) as shapefile:
        # print(shapefile.schema)
        schema = shapefile.schema
        # iterate over the records
        for feat in shapefile:
            # get the geometry from the record
            geometry = shape(feat['geometry'])
            geojson = shapely.to_geojson(geometry)
            parent_geojson["features"].append({'type': 'Feature', 
                                                'properties': json.loads(json.dumps(feat.properties._data)), 
                                                'geometry': json.loads(geojson)
                                             })
            # get attributes
            # for k, v in feat.properties.items():
            #    print(k, v)
            
            # print(feat.geometry['type'])
            # print(feat.geometry['coordinates'])

            # for itm in feat.items():
            #     print(itm)

            # print area of the geometry
            # print(geometry.area)
            # feat['geom'] = shapely.to_geojson(geometry)
            features.append(feat)
    return schema, features, json.dumps(parent_geojson)
    
