# Copyright (c) 2024, Steve Nyaga and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from gis.utils.vector import get_geojson_bounds

class Admin0(Document):
	def validate(self):
		self.bounds = str(get_geojson_bounds(self.geom))
		self.admin_name = self.country
