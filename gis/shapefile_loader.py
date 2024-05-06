import json
import frappe
import pprint

# folder = '/home/nyaga/frappe-bench-15/apps/gis/data/geojson'
folder = '/home/frappe/frappe-bench/apps/gis/data/geojson'
admin_zero_file = f'{folder}/geoBoundaries-KEN-ADM0.geojson'
admin_one_file = f'{folder}/geoBoundaries-KEN-ADM1.geojson'
admin_two_file = f'{folder}/geoBoundaries-KEN-ADM2.geojson'
admin_three_file = f'{folder}/geoBoundaries-KEN-ADM3.geojson'

admin_map = {
    'Makueni': []
}

def _load_admins(admin_level, admin_names: list, parent):
    if not isinstance(admin_names, list):
        admin_names = [admin_names]
    geojson = {}
    source_file, parent_field = '', ''
    if admin_level == 0: #country
        source_file = admin_zero_file
        parent_field = 'continent'
    if admin_level == 1: #county
        source_file = admin_one_file
        parent_field = 'admin_0'
    if admin_level == 2: #sub-counties / wards
        source_file = admin_two_file
        parent_field = 'admin_1'
    if admin_level == 3: #Wards
        source_file = admin_three_file
        parent_field = 'admin_2'

    with open(source_file) as f:
        geojson = json.load(f)
     
    #pprint.pprint(sorted([x['properties']['shapeName'] for x in geojson['features']])) 

    # filter matching features
    matching = [x for x in geojson['features'] if x['properties']['shapeName'] in admin_names]
    for i, feat in enumerate(matching):
        print("Processing {3}. {0}. {1} of {2}".format(feat['properties']['shapeName'], i+1, len(matching), parent))
        exists = frappe.db.exists(f'Admin {admin_level}', {'name': feat['properties']['shapeName'], parent_field: parent})
        if exists:
            continue #do nothing
        doc = frappe.new_doc(f"Admin {admin_level}")
        doc.admin_name = feat['properties']['shapeName']
        doc.geom = json.dumps(feat['geometry'])
        r = {}
        r[parent_field] = parent
        doc.update(r) 
        doc.save(ignore_permissions=True)


def load_admin_zero():
    _load_admins(admin_level=0, admin_names=['Kenya'], parent='Africa')

def load_admin_one():
    # _load_admins(admin_level=1, admin_names=['Makueni'], parent='Kenya')
    _load_admins(admin_level=1, admin_names=['Vihiga'], parent='Kenya')
    
def load_admin_two():
    # _load_admins(admin_level=2, admin_names=['Kaiti'], parent='Makueni')
    # _load_admins(admin_level=2, admin_names=['Kaiti', 'Kilome', 'Makueni', 'Kibwezi East', 'Kibwezi West', 'Mbooni'], parent='Makueni')
    _load_admins(admin_level=2, admin_names=['Vihiga', 'Sabatia', 'Hamisi', 'Luanda', 'Emuhaya'], parent='Vihiga')

def load_admin_three(): 
    def _load_makueni():
        _load_admins(admin_level=3, admin_names=['Kee', 'Kilungu', 'Ilima', 'Ukia'], parent='Kaiti')
        _load_admins(admin_level=3, admin_names=['Kiima Kiu/Kalanzoni', 'Mukaa', 'Kasikeu'], parent='Kilome')
        _load_admins(admin_level=3, admin_names=['Nzaui/Kilili/Kalamba', 'Muvau/Kikuumini', 'Kathonzweni', 'Mavindini', 'Kitise/Kithuki', 'Wote', 'Mbitini'], parent='Makueni')
        _load_admins(admin_level=3, admin_names=['Masongaleni', 'Mtito Andei', 'Thange', 'Ivingoni/Nzambani'], parent='Kibwezi East')
        _load_admins(admin_level=3, admin_names=['Makindu', 'Kikumbulyu North', 'Kikumbulyu South', 'Nguumo', 'Nguu/Masumba', 'Emali/Mulala'], parent='Kibwezi West')
        _load_admins(admin_level=3, admin_names=['Tulimani', 'Mbooni', 'Kithungo/Kitundu', 'Kisau/Kiteta', 'Waia/Kako', 'Kalawa'], parent='Mbooni')
    
    def _load_vihiga():
        _load_admins(admin_level=3, admin_names=['Lugaga-Wamuluma', 'South Maragoli', 'Central Maragoli', 'Mungoma'], parent='Vihiga')
        _load_admins(admin_level=3, admin_names=['Lyaduywa/Izava', 'West Sabatia', 'Chavakali', 'North Maragoli', 'Wodanga', 'Busali'], parent='Sabatia')
        _load_admins(admin_level=3, admin_names=['Shiru', 'Gisambai', 'Shamakhokho', 'Banja', 'Muhudu', 'Tambua', 'Jepkoyai'], parent='Hamisi')
        _load_admins(admin_level=3, admin_names=['Luanda Township', 'Wemilabi', 'Mwibona', 'Luanda South', 'Emabungo'], parent='Luanda')
        _load_admins(admin_level=3, admin_names=['North East Bunyore', 'Central Bunyore', 'West Bunyore'], parent='Emuhaya')

    # _load_makueni()
    _load_vihiga()

def load_all_admins():
    load_admin_zero()
    load_admin_one()
    load_admin_two()
    load_admin_three()
    