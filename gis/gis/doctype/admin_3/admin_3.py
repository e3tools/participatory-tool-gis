# Copyright (c) 2024, Steve Nyaga and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from gis.utils.vector import get_geojson_bounds
from gis.shapefile_loader import download_gadm_data

class Admin3(Document):
	def validate(self):
		self.bounds = str(get_geojson_bounds(self.geom))
		self.admin_name = self.name_3
		download_gadm_data()
