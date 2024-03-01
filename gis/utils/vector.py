import json 
import fiona
import shapely
import frappe
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

def get_admin_tree(as_tree=False):
    """
    Get all admins with the children property set 
    """ 
    admin_0 = frappe.db.get_list("Admin 0", fields=['name', 'admin_name'])
    admin_1 = frappe.db.get_list("Admin 1", fields=['name', 'admin_name', 'admin_0'])
    admin_2 = frappe.db.get_list("Admin 2", fields=['name', 'admin_name', 'admin_1'])
    admin_3 = frappe.db.get_list("Admin 3", fields=['name', 'admin_name', 'admin_2'])
    res = []
    for adm0 in admin_0:
        adm0['children'] = []
        adm0['level'] = 0
        adm0['parent'] = True
        res.append(adm0)
        for adm1 in [x for x in admin_1 if x.admin_0 == adm0.name]:
            adm0['children'].append(adm1)
            adm1['level'] = 1
            adm1['parent'] = True
            adm1['children'] = []
            for adm2 in [x for x in admin_2 if x.admin_1 == adm1.name]:
                adm1['children'].append(adm2)
                adm2['level'] = 2
                adm2['parent'] = True
                adm2['children'] = [] 
                for adm3 in [x for x in admin_3 if x.admin_2 == adm2.name]:
                    adm2['children'].append(adm3)
                    adm3['level'] = 3
                    adm3['children'] = []
                    adm3['parent'] = False
    if as_tree:
        return res
    else:
        nodes = []
        flatten_tree(res, nodes)
        nodes = sorted(nodes, key=lambda k: k['admin_name'], reverse=False)
        return nodes

def flatten_tree(tree, nodes):
    if isinstance(tree, list):
        for child in tree:
            flatten_tree(child, nodes=nodes)
    elif hasattr(tree, 'children') and tree['children']:
        for child in tree['children']:
            flatten_tree(child, nodes=nodes)
    else:
        nodes.append(tree)

def get_admin_doc(admin_id: str, admin_level: int):
    """Get admin object

    Args:
        admin_id (str): Admin id
        admin_level (int): Admin Level. One of 0, 1, 2, 3
    """
    doc = frappe.get_doc(f"Admin {admin_level}", admin_id)
    return doc
