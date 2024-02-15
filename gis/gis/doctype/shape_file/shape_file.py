# Copyright (c) 2024, Steve Nyaga and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from gis.utils.vector import parse_shapefile
from gis.utils.file import get_absolute_path, unzip_file
import datetime
import os
from frappe import _
import shapely
from shapely.geometry import shape
import json

MAX_CUSTOM_FIELDS = 10

class ShapeFile(Document):
	def validate(self):
		self.read_shape_file()

	def read_shape_file(self):
		def infer_table_field(field_type):
			# if field_type.startswith('int'):
			# 	count = get_mapped_field_counts('int')
			# 	return f'int_{count + 1}', 'Integer'
			if field_type.startswith('str'):
				count = get_mapped_field_counts('string')
				return f'string_{count + 1}', 'Text'
			if field_type.startswith('int') or field_type.startswith('float'):
				count = get_mapped_field_counts('float')
				return f'float_{count + 1}', 'Float'
			if field_type.startswith('date'):
				count = get_mapped_field_counts('date')
				return f'date_{count + 1}', 'Date'

		def get_mapped_field_counts(field_type):
			count = len([x for x in self.field_mappings if x.table_field.startswith(field_type)])
			if count == MAX_CUSTOM_FIELDS:
				frappe.throw(_(f"The shape file has more than {MAX_CUSTOM_FIELDS} for type {field_type}"))
			return count

		self.field_mappings = []
		self.items = []
		if not self.zip_file:
			return
		folder = str(datetime.datetime.now())
		dest_dir = os.path.join(get_absolute_path(frappe.utils.get_files_path(is_private=False)), folder)
		files = unzip_file(get_absolute_path(self.zip_file), dest_dir)
		shp_file = [x for x in files if x.endswith('.shp')] 

		if shp_file: 
			schema, features, parent_geojson = parse_shapefile(shp_file[0])
			self.geom = parent_geojson	
			if schema:			
				# define mappings
				for k, v in schema['properties'].items():
					field, field_type = infer_table_field(v)
					kid = self.append('field_mappings', {
						'doctype': 'Shape File Field Mapping',
						'attribute': k,
						'attribute_data_type': v,
						'table_field': field,
						'table_field_data_type': field_type
					})
			frappe.utils.file_manager.delete_file(dest_dir)

			# generate entries
			if features:
				for feat in features:
					rec = {
						'doctype': 'Shape File Item'
					}
					for mp in self.field_mappings:
						rec[mp.table_field] = feat.properties[mp.attribute]

					rec['geom'] = shapely.to_geojson(shape(feat['geometry'])) # feat['geom']
					kid = self.append('items', rec)

@frappe.whitelist()
def get_shape_file_field_mappings(shape_file):
	doc = frappe.get_doc("Shape File", shape_file)
	return { "field_mappings": doc.field_mappings }