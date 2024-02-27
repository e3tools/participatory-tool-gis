# Copyright (c) 2024, Steve Nyaga and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class Legend(Document):
	def validate(self):
		if not self.sld_layer and not self.legend_entries:
			frappe.throw(_("You must specify either the legend entries or the SLD Layer"))