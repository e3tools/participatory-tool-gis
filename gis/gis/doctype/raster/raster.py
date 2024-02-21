# Copyright (c) 2024, Steve Nyaga and contributors
# For license information, please see license.txt

import frappe
import gis.defaults as DEFAULTS
from frappe.model.document import Document
from gis.utils.raster import get_raster_meta

class Raster(Document):
	def validate(self):
		self.get_metadata()

	def get_metadata(self):
		if self.raster_file:
			meta = get_raster_meta(self.raster_file, set_default_nodata=False)
			if meta:
				self.nodata = meta.get('nodata') if 'nodata' in meta and meta['nodata'] else DEFAULTS.NODATA
				self.max_zoom = meta.get('max_zoom') if 'max_zoom' in meta else 0
				self.srid = meta['crs'] if 'crs' in meta and meta['crs'] else DEFAULTS.SRID
