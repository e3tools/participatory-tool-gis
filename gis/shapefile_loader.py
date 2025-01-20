import json
import frappe
import pprint
import requests
import tqdm
import logging
import os 
import geopandas as gpd
import pathlib
import getpass

user = getpass.getuser() #nyaga #frappe
folder = f'/home/{user}/frappe-bench-15/apps/gis/data/geojson'
# folder = '/home/frappe/frappe-bench/apps/gis/data/geojson'
admin_zero_file = f'{folder}/geoBoundaries-KEN-ADM0.geojson'
admin_one_file = f'{folder}/geoBoundaries-KEN-ADM1.geojson'
admin_two_file = f'{folder}/geoBoundaries-KEN-ADM2.geojson'
admin_three_file = f'{folder}/geoBoundaries-KEN-ADM3.geojson'

COUNTRY = 0
COUNTY = 1
SUB_COUNTY = 2
WARD = 3
LOCATION = 4
SUB_LOCATION = 5

COUNTRY_DOCTYPE = f'Admin {COUNTRY}'
COUNTY_DOCTYPE = f'Admin {COUNTY}'
SUB_COUNTY_DOCTYPE = f'Admin {SUB_COUNTY}'
WARD_DOCTYPE = f'Admin {WARD}'
LOCATION_DOCTYPE = f'Admin {LOCATION}'
SUB_LOCATION_DOCTYPE = f'Admin {SUB_LOCATION}'

admin_map = {
	'Makueni': []
}

def load_cascaded_county_admins():
	"""
	Use this function since it has updated vectors and also provides for cascaded loads 
	"""
	folder = f'/home/{user}/frappe-bench-15/apps/gis/data/geojson/humdata'
	# folder = '/home/frappe/frappe-bench/apps/gis/data/geojson'
	admin_zero_file = f'{folder}/kenya_country.geojson'
	admin_one_file = f'{folder}/kenya_counties.geojson'
	admin_two_file = f'{folder}/kenya_sub_counties.geojson'
	admin_three_file = f'{folder}/kenya_wards.geojson'  

	def _load_admin_geojsons():
		print ("Reading admin zero...")
		with open(admin_zero_file) as f:
			admin_zero = json.load(f)

		print ("Reading admin one...")
		with open(admin_one_file) as f:
			admin_one = json.load(f)

		print ("Reading admin two...")
		with open(admin_two_file) as f:
			admin_two = json.load(f)

		print ("Reading admin three...")
		with open(admin_three_file) as f:
			admin_three = json.load(f)

		return [admin_zero, admin_one, admin_two, admin_three]
 
	def _load_country():
		country = "Kenya"
		admin_name_field = 'shapeName'
		matching = [x for x in admin_zero_geojson['features'] if x['properties'][admin_name_field] in [country]]
		print(f"Processing Country {country}")
		_process_admin(admin_level=COUNTRY, admin=matching[0], parent_admin="Africa")

	def _load_county(counties: str):
		if not isinstance(counties, list):
			counties = [counties]
 
		admin_name_field = 'county'
		matching = [x for x in admin_one_geojson['features'] if x['properties'][admin_name_field] in counties]
		for i, match in enumerate(matching):
			county = match['properties'][admin_name_field]
			print(f"Processing County {county}. {i+1} of {len(matching)}")
			
			# Save parent else Link Does Not Exist exception will be thrown
			_process_admin(admin_level=COUNTY, admin=match, parent_admin="Kenya")

			sub_counties = _get_child_admins(SUB_COUNTY, county)
			for i, sub_county in enumerate(sub_counties):
				print(">" * SUB_COUNTY, "Processing {0}. {1}. {2} of {3}".format('Sub County', sub_county, i+1, len(sub_counties)))
				_load_sub_county(sub_county, county) 			

	def _load_sub_county(sub_county: str, county: str):
		admin_name_field = 'subcounty'
		matching = [x for x in admin_two_geojson['features'] if x['properties'][admin_name_field] in [sub_county]]
		for i, match in enumerate(matching):
			# Save parent else Link Does Not Exist exception will be thrown
			_process_admin(admin_level=SUB_COUNTY, admin=match, parent_admin=county)
			wards = _get_child_admins(WARD, sub_county)
			for i, ward in enumerate(wards):
				print("=" * WARD, "Processing {0}. {1}. {2} of {3}".format('Ward', ward, i+1, len(wards)))
				_load_ward(ward, sub_county)
	
	def _load_ward(ward: str, sub_county: str):
		# _process_admin(admin_level=WARD, admin=ward, parent_admin=sub_county)
		admin_name_field = 'ward'
		matching = [x for x in admin_three_geojson['features'] if x['properties'][admin_name_field] in [ward]]
		_process_admin(admin_level=WARD, admin=matching[0], parent_admin=sub_county)
			
	def _get_child_admins(child_admin_level, parents) -> list[str]:
		if not isinstance(parents, list):
			parents = [parents]
		
		geojson = {}
		# if child_admin_level == COUNTRY: #country
		# 	geojson = admin_zero_geojson
		# 	parent_field = 'continent'
		# 	source_admin_name_field = 'shapeName'
		if child_admin_level == COUNTY: #county
			geojson = admin_one_geojson
			parent_field = 'country'
			source_admin_name_field = 'county'
		if child_admin_level == SUB_COUNTY: #sub-counties
			geojson = admin_two_geojson
			parent_field = 'county'
			source_admin_name_field = 'subcounty'
		if child_admin_level == WARD: #Wards
			geojson = admin_three_geojson
			parent_field = 'subcounty'
			source_admin_name_field = 'ward'

		children = [x for x in geojson['features'] if x['properties'][parent_field] in parents]
		return [x['properties'][source_admin_name_field] for x in children]
	
	def _process_admin(admin_level: int, admin: dict, parent_admin: str): 
		# if not isinstance(admin_names, list):
		# 	admin_names = [admin_names]
		geojson = {}
		source_file, parent_field, source_admin_name_field, source_parent_field, strip_suffix, parent_strip_suffix, admin_type  = '', '', '', '', '', '', ''
		if admin_level == COUNTRY: #country
			admin_type = 'Country'
			source_file = admin_zero_file
			parent_field = 'continent'
			source_admin_name_field = 'shapeName'
			strip_suffix = ''
			parent_strip_suffix = ''
		if admin_level == COUNTY: #county
			admin_type = 'County'
			source_file = admin_one_file
			parent_field = 'admin_0'
			source_admin_name_field = 'county'
			strip_suffix = 'County'
			parent_strip_suffix = ''
		if admin_level == SUB_COUNTY: #sub-counties 
			admin_type = 'Sub County'
			source_file = admin_two_file
			parent_field = 'admin_1'
			source_admin_name_field = 'subcounty'
			strip_suffix = 'Sub County'
			parent_strip_suffix = ''
		if admin_level == WARD: #Wards
			admin_type = 'Ward'
			source_file = admin_three_file
			parent_field = 'admin_2'
			source_admin_name_field = 'ward'
			strip_suffix = 'Ward'
			parent_strip_suffix = 'Sub County'

		parent_admin = sanitize_admin_name(parent_admin, parent_strip_suffix)
		# with open(source_file) as f:
		# 	geojson = json.load(f)
		
		#pprint.pprint(sorted([x['properties'][source_admin_name_field] for x in geojson['features']])) 

		# filter matching features
		matching = [admin] # [x for x in geojson['features'] if x['properties'][source_admin_name_field] in admin_names]
		for i, feat in enumerate(matching):
			admin_name = feat['properties'][source_admin_name_field]
			# print(" " * admin_level, "Processing {3}. {0}. {1} of {2}".format(admin_name, i+1, len(matching), admin_type))
			if strip_suffix:
				admin_name = sanitize_admin_name(admin_name, strip_suffix)

			if not admin_name:
				frappe.throw("Admin name cannot be empty")
			
			if admin_level == COUNTRY:
				exists = frappe.db.exists(f'Admin {admin_level}', {'name': admin_name})
			else:
				exists = frappe.db.exists(f'Admin {admin_level}', {'name': admin_name, 'parent_admin': parent_admin})
			if exists:
				continue #do nothing
			doc = frappe.new_doc(f"Admin {admin_level}")
			doc.admin_name = admin_name
			doc.geom = json.dumps(feat['geometry'])
			r = {}
			r[parent_field] = parent_admin
			doc.parent_admin = parent_admin
			doc.update(r) 
			doc.save(ignore_permissions=True)

	def _load_recursive(county):
		# _load_admin_geojsons()
		_load_country()
		_load_county(county)
	
	admin_zero_geojson, admin_one_geojson, admin_two_geojson, admin_three_geojson = _load_admin_geojsons()

	_load_recursive("Nyeri")

def sanitize_admin_name(text, suffix):
	words = suffix.split(' ')
	words.reverse()
	for word in words:
		text = str(text).lower().rstrip(str(word).lower()).strip()
	return text.title()

def _load_admins(admin_level, admin_names: list, parent):
	if not isinstance(admin_names, list):
		admin_names = [admin_names]
	geojson = {}
	source_file, parent_field = '', ''
	if admin_level == COUNTRY: #country
		source_file = admin_zero_file
		parent_field = 'continent'
	if admin_level == COUNTY: #county
		source_file = admin_one_file
		parent_field = 'admin_0'
	if admin_level == SUB_COUNTY: #sub-counties / wards
		source_file = admin_two_file
		parent_field = 'admin_1'
	if admin_level == WARD: #Wards
		source_file = admin_three_file
		parent_field = 'admin_2'

	with open(source_file) as f:
		geojson = json.load(f)
	
	#pprint.pprint(sorted([x['properties']['shapeName'] for x in geojson['features']])) 

	# filter matching features
	matching = [x for x in geojson['features'] if x['properties']['shapeName'] in admin_names]
	for i, feat in enumerate(matching):
		print("Processing {3}. {0}. {1} of {2}".format(feat['properties']['shapeName'], i+1, len(matching), parent))
		exists = frappe.db.exists(f'Admin {admin_level}', {'name': feat['properties']['shapeName'], 'parent_admin': parent})
		if exists:
			continue #do nothing
		doc = frappe.new_doc(f"Admin {admin_level}")
		doc.admin_name = feat['properties']['shapeName']
		doc.geom = json.dumps(feat['geometry'])
		r = {}
		r[parent_field] = parent
		doc.parent_admin = parent
		doc.update(r) 
		doc.save(ignore_permissions=True)

def load_admin_zero():
	_load_admins(admin_level=COUNTRY, admin_names=['Kenya'], parent='Africa')

def load_admin_one(): 
	def _do_load(admin_name):
		_load_admins(admin_level=COUNTY, parent='Kenya', admin_names=[admin_name], strip_suffix='County')

	_do_load(admin_name='Makueni')
	_do_load(admin_name='Vihiga')
	_do_load(admin_name='Nyeri')
	
def load_admin_two():
	def _do_load(parent, admin_names):
		_load_admins(admin_level=SUB_COUNTY, parent='Kenya', admin_names=admin_names, strip_suffix='Sub County')

	# _load_admins(admin_level=2, admin_names=['Kaiti'], parent='Makueni') 
	# _do_load(parent='Makueni', admin_names=['Kaiti', 'Kilome', 'Makueni', 'Kibwezi East', 'Kibwezi West', 'Mbooni'])
	# _do_load(parent='Vihiga', admin_names=['Vihiga', 'Sabatia', 'Hamisi', 'Luanda', 'Emuhaya']) 
	_do_load(parent='Nyeri', admin_names=['Kieni East', 'Kieni West', 'Mathira East', 'Mathira West', 'Nyeri Central', 'Mukurweini', 'Othaya', 'Tetu'])
 

def load_admin_three(): 
	def _do_load(parent, admin_names):
		_load_admins(admin_level=WARD, parent=parent, admin_names=admin_names, strip_suffix='Ward')

	def _load_makueni():
		_do_load(parent='Kaiti', admin_names=['Kee', 'Kilungu', 'Ilima', 'Ukia'])
		_do_load(parent='Kilome', admin_names=['Kiima Kiu/Kalanzoni', 'Mukaa', 'Kasikeu'])
		_do_load(parent='Makueni', admin_names=['Nzaui/Kilili/Kalamba', 'Muvau/Kikuumini', 'Kathonzweni', 'Mavindini', 'Kitise/Kithuki', 'Wote', 'Mbitini'])
		_do_load(parent='Kibwezi East', admin_names=['Masongaleni', 'Mtito Andei', 'Thange', 'Ivingoni/Nzambani'])
		_do_load(parent='Kibwezi West', admin_names=['Makindu', 'Kikumbulyu North', 'Kikumbulyu South', 'Nguumo', 'Nguu/Masumba', 'Emali/Mulala'])
		_do_load(parent='Mbooni', admin_names=['Tulimani', 'Mbooni', 'Kithungo/Kitundu', 'Kisau/Kiteta', 'Waia/Kako', 'Kalawa'])
	
	def _load_vihiga():
		_do_load(parent='Vihiga', admin_names=['Lugaga-Wamuluma', 'South Maragoli', 'Central Maragoli', 'Mungoma'])
		_do_load(parent='Sabatia', admin_names=['Lyaduywa/Izava', 'West Sabatia', 'Chavakali', 'North Maragoli', 'Wodanga', 'Busali'])
		_do_load(parent='Hamisi', admin_names=['Shiru', 'Gisambai', 'Shamakhokho', 'Banja', 'Muhudu', 'Tambua', 'Jepkoyai'])
		_do_load(parent='Luanda', admin_names=['Luanda Township', 'Wemilabi', 'Mwibona', 'Luanda South', 'Emabungo'])
		_do_load(parent='Emuhaya', admin_names=['North East Bunyore', 'Central Bunyore', 'West Bunyore'])

	def _load_nyeri():
		_do_load(parent='Kieni East', admin_names=['Gakawa', 'Naromoru Kiamathaga', 'Kabaru', 'Thegu River'])
		_do_load(parent='Kieni West', admin_names=['Mweiga', 'Mwiyogo/Endarasha', 'Mugunda', 'Gatarakwa'])
		_do_load(parent='Mathira East', admin_names=['Karatina Town', 'Iriaini', 'Konyu', 'Magutu'])
		_do_load(parent='Mathira West', admin_names=['Kirimukuyu', 'Ruguru'])
		_do_load(parent='Mukurweini', admin_names=['Gikondi', 'Rugi', 'Mukurwe-Ini West', 'Mukurwe-Ini Central'])
		_do_load(parent='Nyeri Central', admin_names=['Kiganjo/Mathari', 'Rware', 'Gatitu/Muruguru', "Ruring'U", 'Kamakwa/Mukaro'])
		_do_load(parent='Othaya', admin_names=['Chinga', 'Karima', 'Mahiga', 'Iria-Ini'])
		_do_load(parent='Tetu', admin_names=['Dedan Kimanthi', 'Wamagana', 'Aguthi-Gaaki'])

	# _load_makueni()
	# _load_vihiga()
	_load_nyeri()

def load_all_admins():
	load_admin_zero()
	load_admin_one()
	load_admin_two()
	load_admin_three()

def load_full_admin_tree(county_to_process='Makueni'):
	"""
	Import all admin levels in the order of levels
	Data downloaded from https://data.humdata.org/ and https://github.com/konektaz/shape-files
	"""
	def _process_country():
		# _load_admins(admin_level=COUNTRY, admin_names=['Kenya'], parent='Africa')
		source_file = f'{data_folder}/kenya_country.geojson'
		_do_process(source_file, admin_level=COUNTRY, name_property='shapeName', parent_property=None, 
					parent_field='parent_admin')

	def _process_counties():
		source_file = f'{data_folder}/kenya_counties.geojson'
		_do_process(source_file, admin_level=COUNTY, name_property='county', parent_property='country', 
					parent_field='parent_admin')

	def _process_sub_counties():
		source_file = f'{data_folder}/kenya_sub_counties.geojson'
		_do_process(source_file, admin_level=SUB_COUNTY, name_property='subcounty', 
					parent_property='county', parent_field='parent_admin', suffix='Sub County',
					cluster_property='province')

	def _process_wards():
		source_file = f'{data_folder}/kenya_wards.geojson'
		_do_process(source_file, admin_level=WARD, name_property='ward', 
					parent_property='subcounty', parent_field='parent_admin', suffix='Ward', 
					parent_suffix='Sub County', cluster_property='county')

	# def _process_locations():
	#     source_file = f'{data_folder}/kenya_locations.geojson'
	#     _do_process(source_file, admin_level=LOCATION, name_property='ward', 
	#                 parent_property='county', parent_field='parent_admin', suffix='Sub County')

	def _process_sub_locations():
		"""
		Data downloaded from https://github.com/4adb7a60-1622-4152-9567-e8f27d1627f3
		We will use sub_locations file to deduce locations
		For each sublocation, we will lookup if the name of location from locations geojson file. If the 
		entry is found, then save that location and then proceed to save the sub-location
		"""
		source_file = f'{data_folder}/kenya_sub_locations.geojson'
		_do_process(source_file, admin_level=SUB_LOCATION, name_property='SLNAME', 
					parent_property='LOCNAME', parent_field='parent_admin', suffix=None,
					cluster_property='DISTNAME')
		
	def _get_sub_county(doc):
		if doc.doctype == COUNTY_DOCTYPE:
			return doc.admin_name
		if doc.doctype == SUB_COUNTY_DOCTYPE:
			return doc.parent_admin
		if doc.doctype == WARD_DOCTYPE:
			return frappe.db.get_value(SUB_COUNTY_DOCTYPE, doc.parent_admin, 'parent_admin')
		if doc.doctype == LOCATION_DOCTYPE:
			# get subcounty
			sub_county = frappe.db.get_value(WARD_DOCTYPE, doc.parent_admin, 'parent_admin')
			return frappe.db.get_value(SUB_COUNTY_DOCTYPE, sub_county, 'parent_admin')
		if doc.doctype == SUB_LOCATION_DOCTYPE:
			# get ward
			ward = frappe.db.get_value(LOCATION_DOCTYPE, doc.parent_admin, 'parent_admin')
			# get subcounty
			sub_county = frappe.db.get_value(WARD_DOCTYPE, ward, 'parent_admin')
			return frappe.db.get_value(SUB_COUNTY_DOCTYPE, sub_county, 'parent_admin')
		return None
	
	def _do_process(source_file: str, admin_level: int, name_property: str, parent_property: str, admin_names: list = [], 
					parent: str = None, parent_field: str = None, suffix: str=None, parent_suffix: str=None,
					cluster_property: str = None):
		"""Load geojson into the database

		Args:
			source_file (str): geojson file
			admin_level (int): Admin level one of 0|1|2|3|4|5
			name_property (str): Which property in the geojson file will be used to uniquely identify an admin
			parent_property (str): Which property in the geojson file holds the parent admin name
			admin_names (list, optional): List of admin_names that should be loaded. Use when you want to load specific admins. Defaults to []
			parent (str, optional): The parent of the admin levels. Defaults to None
			parent_field (str, optional): The field in the database that holds the parent of an admin. Defaults to None.
			suffix (str, optional): The text to be stripped from name_property. Defaults to None.
			parent_suffix (str, optional): The text to be stripped from parent_property. Defaults to None.
		"""

		def _sanitize_name(name: str, sfx=suffix):
			return sanitize_name(name, suffix=sfx)
		
		def make_admin_name(admin_name: str, parent_val: str):
			"""Attempt to get a name to be used for an admin.
			If there are multiple items with the same name, this function returns a concatenation of admin_name and parent_val

			Args:
				admin_name (str): Admin name
				parent_val (str): Name of parent
			"""
			# check if there is another admin sharing the same name
			counts = [x for x in geojson['features'] if _sanitize_name(x['properties'][name_property]) == admin_name]
			if len(counts) > 1:
				# there exists multiple admins with same name, so rename the existing
				return f'{admin_name} - {parent_val}'
			return admin_name

		def _save_location(location_name, subcounty_name, locations: list=[], cluster_property='DISTNAME'): 
			matching = [x for x in locations['features'] if _sanitize_name(x['properties']['LOCNAME']) == _sanitize_name(location_name)]
			if matching:                
				loc = matching[0]
				admin_name_val = _sanitize_name(location_name, sfx=None) 
				docname = make_admin_name(admin_name_val, subcounty_name)
				# if not admin_name_val:
				#     import pdb; pdb.set_trace()
				# print("Processing location {0}".format(location_name))
				# exists = frappe.db.exists(doctype, {'name': admin_name_val,  parent_field: parent_val})
				exists = frappe.db.exists(LOCATION_DOCTYPE, {'name': docname})
				if exists:
					# continue #do nothing
					doc = frappe.get_doc(LOCATION_DOCTYPE, docname)
				else:
					doc = frappe.new_doc(LOCATION_DOCTYPE)
				r = loc['properties']
				if cluster_property:
					r['cluster'] = loc['properties'][cluster_property]      

				if frappe.db.exists(SUB_COUNTY_DOCTYPE, _sanitize_name(subcounty_name)):
					r[parent_field] = _sanitize_name(subcounty_name)
					doc.update(r)
					doc.admin_name = docname
					doc.geom = json.dumps(loc['geometry'])
					if _get_sub_county(doc) == county_to_process:
						doc.save(ignore_permissions=True)
						return doc.name
				# check if location is already saved
				return frappe.db.exists(LOCATION_DOCTYPE, docname)
			return None

		print("Processing started...")
		# load json file
		with open(source_file) as f:
			geojson = json.load(f)
		
		#pprint.pprint(sorted([x['properties']['shapeName'] for x in geojson['features']]))
		
		# finish loading locations

		locations = []
		if admin_level == SUB_LOCATION:
			# load locations 
			loc_file = f'{data_folder}/kenya_locations.geojson'
			with open(source_file) as f:
				locations = json.load(f)

		admin_names = [_sanitize_name(x) for x in admin_names]

		doctype = f'Admin {admin_level}'
		# filter matching features
		matching = [x for x in geojson['features'] if _sanitize_name(x['properties'][name_property]) in admin_names] if admin_names else geojson['features']
		locations_not_processed = []
		for i, feat in enumerate(matching):
			admin_name_val = _sanitize_name(feat['properties'][name_property], sfx=suffix)

			location_name = None
			if admin_level == SUB_LOCATION:
				# lookup location
				location_name = _save_location(feat['properties']['LOCNAME'], feat['properties']['DIVNAME'], locations=locations)
				parent_val = location_name
				if not location_name:
					locations_not_processed.append({"sub-county": feat['properties']['DIVNAME'], "location": feat['properties']['LOCNAME'], "sublocation": feat['properties'][name_property]})
					continue 
			elif admin_level != COUNTRY: 
				parent_val = _sanitize_name(feat['properties'][parent_property], sfx=parent_suffix)
			else:
				parent_val = None #countries have no parent admin
			
			docname = make_admin_name(admin_name_val, parent_val)
			# if not admin_name_val:
			#     import pdb; pdb.set_trace()
			print("Processing {0}. {1} of {2}".format(admin_name_val, i+1, len(matching)))
			# exists = frappe.db.exists(doctype, {'name': admin_name_val,  parent_field: parent_val})
			exists = frappe.db.exists(doctype, {'name': docname})
			if exists:
				# continue #do nothing
				doc = frappe.get_doc(doctype, docname)
			else:
				doc = frappe.new_doc(doctype)
			r = feat['properties']
			if cluster_property:
				r['cluster'] = feat['properties'][cluster_property]      
			r[parent_field] = parent_val
			doc.update(r)
			doc.admin_name = docname
			doc.geom = json.dumps(feat['geometry']) 
			if admin_level == COUNTRY:
				doc.save(ignore_permissions=True)
			else:
				if _get_sub_county(doc) == county_to_process:
					doc.save(ignore_permissions=True)

		if locations_not_processed:
			print("\nSub-counties not processed: ", sorted(list(set([x['sub-county'] for x in locations_not_processed if x['sub-county']]))))
			print("\nLocations not processed: ", sorted(list(set([x['location'] for x in locations_not_processed if x['location']]))))
			print("\nSub-Locations not processed: ", sorted(list(set([x['sublocation'] for x in locations_not_processed if x['sublocation']]))))

	# data_folder = '/home/nyaga/frappe-bench-15/apps/gis/data/geojson/humdata'
	parent_folder = os.path.abspath(os.path.join(os.getcwd(), ".."))
	data_folder = os.path.join(parent_folder, "apps", "gis", "data", "geojson", "humdata")
	
	_process_country()
	# _process_counties()
	# _process_sub_counties()
	# _process_wards()
	# _process_sub_locations() # will import locations too
	pass    

def sanitize_name(name: str, suffix: str = None):
	# name = name.strip(suffix or '') # do not use strip as strip replaces a character at a time thus may mess the orginal value
	name = name.strip() if name else ''
	if suffix:
		tot_len = len(name)
		sfx_len = len(suffix)
		if name[tot_len - sfx_len:] == suffix:
			name = name[:-len(suffix)].strip() 
	return frappe.unscrub(name.replace("'", ""))

def download_gadm_data(country_iso3='KEN', timeout_sec: float = 180, logger: logging.Logger = logging.getLogger()) -> None:
	"""
	Download data for a country from www.gadm.org that comes in form of geopandas package
	To download the full world data, go to https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-gpkg.zip
	"""

	def make_admin_name(admin_name: str, parent_val: str, admin_type: str, admin_level: int, name_property: str):
		"""Attempt to get a name to be used for an admin.
		If there are multiple items with the same name, this function returns a concatenation of admin_name and parent_val

		Args:
			admin_name (str): Admin name
			parent_val (str): Name of parent
		"""
		# check if there is another admin sharing the same name
		# counts = [x for x in geojson['features'] if _sanitize_name(x['properties'][name_property]) == admin_name]
		recs = geodb[(geodb[f'ENGTYPE_{admin_level}']== admin_type) & (geodb['GID_0']==country_iso3)]
		if recs.shape[0] > 1:
			# there exists multiple admins with same name, so rename the existing 
			return f'{admin_name} - {parent_val}'
		return admin_name
	
	def save_admin(entry, doctype, admin_name, name_property, admin_level, admin_dict):
		docname = admin_name #admin_dict[name_property]
		exists = frappe.db.exists(doctype, {'name': docname})
		if exists:
			# continue #do nothing
			doc = frappe.get_doc(doctype, docname)
		else:
			doc = frappe.new_doc(doctype)
		r = admin_dict
		# if cluster_property:
		#     r['cluster'] = feat['properties'][cluster_property]            
		# r[parent_field] = parent_val
		doc.update(r)
		doc.admin_name = docname
		doc.geom = entry.to_json(show_bbox=True)['geometry']
		doc.save(ignore_permissions=True)

	gadm_version='4.1'
	gadm_version_no_dot = gadm_version.replace('.', '')
	url = f'https://geodata.ucdavis.edu/gadm/gadm{gadm_version}/gpkg/gadm{gadm_version_no_dot}_{country_iso3}.gpkg'
	res = requests.head(url)
	assert "Content-Length" in res.headers
	file_size = int(res.headers["Content-Length"])

	dest_file = f'gadm{gadm_version_no_dot}_{country_iso3}.gpkg'
	file_path = frappe.get_site_path(dest_file)
	# file_path = '/home/nyaga/frappe-bench-15/apps/gis/data/shapefiles/gadm_410.gpkg'
	file_path = '/home/nyaga/frappe-bench-15/apps/gis/data/shapefiles/gadm41_KEN.gpkg'
	if not os.path.exists(file_path):
		# If file does not exist, download it
		try:
			response = requests.get(url, stream=True, timeout=timeout_sec, headers=None)
		except requests.exceptions.Timeout as e:
			logger.exception(f"Failed to fetch data due to timeout: {e}")

		with open(file_path, "wb") as fl:
			pbar = tqdm.tqdm(total=file_size, unit="B", unit_scale=True)
			for chunk in response.iter_content(chunk_size=1024):
				if chunk:
					fl.write(chunk)
				pbar.update(len(chunk))
			pbar.close()

	geodb = gpd.read_file(file_path) 
	geodb.set_index('fid') #use UID as the index
	geodb.describe()
	geodb.head(1).T

	# get admin by country
	country_admins = geodb[geodb['GID_0']==country_iso3]

	# get unique country name
	gpd.pd.unique(geodb['NAME_0'])

	# get counties in Kenya
	# counties = gpd.pd.unique(geodb[(geodb['ENGTYPE_1']=='County') & (geodb['GID_0']==country_iso3)]['NAME_1'])

	def load_counties(): 
		_load_admins(id_property='GID_1', admin_type_property='', parent_property='country')

	def _load_admins(id_property: str, name_property: str, admin_level: int, parent_property: str):
		admin_type = None
		doctype = f'Admin {admin_level}'
		if admin_level == COUNTY:
			admin_type = 'County'
		elif admin_level == SUB_COUNTY:
			admin_type = 'Constituency'
		elif admin_level == WARD:
			admin_type = 'Ward'
		elif admin_level == LOCATION:
			admin_type = 'Location'
		elif admin_level == SUB_LOCATION:
			admin_type = 'Sub-Location'

		import pdb; pdb.set_trace()

		groups = geodb[(geodb[f'ENGTYPE_{admin_level}']== admin_type) & (geodb['GID_0']==country_iso3)].groupby([id_property])
		# data is in the form of {'KEN.9_1': [197068, 197069, 197070], 'KEN.9.2: [197071, 197072, 197073, 197074, 197075, 197076, 197077]}
		for gid_1 in groups:
			for uid in groups[gid_1]:
				entry = geodb[geodb['UID'] == uid]            
				# if entry.shape[0] == 1:
				#     rc = entry.to_dict('records') # generate a dict
				#     admin_name = rc[name_property]
				#     admin_name = make_admin_name(admin_name=admin_name, parent_val=rc[parent_property], admin_type=admin_type, admin_level=admin_level, name_property=name_property)
				#     save_admin(entry=entry, doctype=doctype, name_property='name_1', admin_level=admin_level, parent_property=parent_property)
				# elif entry.shape[0] > 1:
				for idx, row in entry.iterrows():
					rc = row.to_dict('records') # generate a dict
					admin_name = rc[name_property]
					admin_name = make_admin_name(admin_name=admin_name, parent_val=rc[parent_property], admin_type=admin_type, admin_level=admin_level, name_property=name_property)
					save_admin(entry=entry, doctype=doctype, name_property='name_1', admin_level=admin_level, parent_property=parent_property)

	load_counties()
	# # merge all counties into country
	# county = geodb[geodb['NAME_1'] == 'Makueni'].unary_union
	# type(county)    