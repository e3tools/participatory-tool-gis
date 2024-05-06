# Import the library
from geo.Geoserver import Geoserver #, GeoserverException
import os
from gis.utils.settings import get_gis_settings
import frappe
from pysld.style import RasterStyle#, Style 
import re
import requests
from gis.utils.sld import style_from_legend

class GeoServerHelper:
	def __init__(self, legend_name, nodata, workspace="participatory"): 
		# Initialize the library
		self.conf = frappe.conf
		self.host_public = self.conf.GEOSERVER_HOST_PUBLIC
		self.host_private = self.conf.GEOSERVER_HOST_PRIVATE
		self.ignore_private_host = self.conf.GEOSERVER_IGNORE_PRIVATE_HOST
		self.port = self.conf.GEOSERVER_PORT
		username = self.conf.GEOSERVER_USERNAME
		password = self.conf.GEOSERVER_PASSWORD
		self.site_url = "/geoserver"

		# print("GEOSERVER_IGNORE_PRIVATE_HOST: ", settings.GEOSERVER_IGNORE_PRIVATE_HOST)
		# print("GEOSERVER_HOST_PUBLIC: ", settings.GEOSERVER_HOST_PUBLIC)
		# print("GEOSERVER_HOST_PRIVATE: ", settings.GEOSERVER_HOST_PRIVATE)

		self.private_url = "{0}:{1}{2}".format(self.host_public if self.ignore_private_host=='1' else self.host_private, self.port, self.site_url)
		self.public_url = "{0}:{1}{2}".format(self.host_public, self.port, self.site_url)

		# print("Public url: ", self.public_url)
		# print("Private url: ", self.private_url)
		# print("Geoserver create attempt...")
		self.geo = Geoserver(service_url=self.private_url, username=username, password=password)
		# print("Geoserver created...")
		self.workspace = workspace
		self.legend_name = legend_name
		self.legend_items = frappe.get_doc('Legend', legend_name).legend_entries # analysis_enum
		# self.computation_type = computation_type		
		self.nodata = nodata
		self.sld = None
		self.style_name = legend_name.strip() # re.search("'\w+'", str(legend_name)).group().strip("'")
		if workspace: 
			self.create_workspace(workspace)
		
	def get_style_xml(self):
		# def get_style(self, style_name, workspace: Optional[str] = None):
		"""
		Returns the style XML by style name.
		"""
		try:
			url = "{}/rest/styles/{}.sld".format(self.geo.service_url, self.style_name)
			if self.workspace is not None:
				url = "{}/rest/workspaces/{}/styles/{}.sld".format(
					self.geo.service_url, self.workspace, self.style_name
				)

			r = requests.get(url, auth=(self.geo.username, self.geo.password))
			return r.text# r.json()

		except Exception as e:
			return "get_style error: {}".format(e)

	def create_workspace(self, workspace):
		"""Create workspace

		Args:
			workspace (string): Workspace name
		"""
		exists = None
		try:
			exists = self.geo.get_workspace(workspace=workspace)
		except Exception as e:
			if e.status == 404:
				if not exists or "Error " in exists:
					self.geo.create_workspace(workspace=workspace) 
		self.workspace = workspace

	def upload_raster(self, raster_path, workspace=None, layer_name=None):
		"""For uploading raster data to the geoserver

		Args:
			raster_path (string): Absolute raster file path e.g r'path\to\raster\file.tif'
			workspace (string, optional): Workspace name. Defaults to the workspace name specified at init
			layer_name (str, optional): Layer Name. Defaults to None.
		"""
		def parse_style_xml(xml):
			"""Replace the nodata place holder with actual nodata value
			"""
			return str(xml).replace(str(self.conf.NODATA_PLACEHOLDER), str(self.nodata))

		def preprocess_xml(xml):
			return xml.replace(" ", "").replace("\n", "").replace("\r", "")

		if not layer_name:
			layer_name = os.path.splitext(os.path.basename(raster_path))[0]
		res = self.geo.create_coveragestore(path=raster_path, 
					layer_name=layer_name, 
					workspace=workspace or self.workspace)
		# self.geo.create_coveragestyle(raster_path=raster_path, 
		# 							  style_name=layer_name, 
		# 							  number_of_classes=len(self.analysis_enum)
		# 							)		
		
		sld_xml = self.is_style_defined()
		if sld_xml:
			sld_xml = parse_style_xml(sld_xml)
				
		# Check if a previous sld has been uploaded 
		existing_style = self._retrieve_style()
		if not existing_style:
			sld_file = self.save_style_to_disk(sld_xml) if sld_xml else self._generate_style()
			res = self.geo.upload_style(path=sld_file, name=self.style_name, workspace=self.workspace)
			# print("upload_style: ", res)
		elif existing_style and sld_xml: # if style is existing, check if published style is diff from the current one. If yes replace		
			# old_xml = self.get_style_xml()
			# if preprocess_xml(old_xml) != preprocess_xml(sld_xml):
			# 	sld_file = self.save_style_to_disk(sld_xml)
			# 	self.geo.upload_style(path=sld_file, name=self.style_name, workspace=self.workspace)			
			pass
		# associate layer with style
		res = self.geo.publish_style(layer_name=layer_name, style_name=self.style_name, workspace=self.workspace)
		# print("publish_style: ", res)
		# delete sld file from disk
		if not existing_style:			
			os.remove(sld_file)
		return self._generate_tile_url(raster_path)
	
	def _retrieve_style(self):
		"""
		Get already uploaded style that is associated with the change enum
		"""
		try:
			res = self.geo.get_style(self.style_name, self.workspace)
			if "get_style error" in res:
				return None
		except Exception as e:
			if e.status == 404:
				return False
		return res

	def is_style_defined(self):
		"""
		Check if the SLD style is defined from Django admin PublishedComputation
		""" 
		obj = self.get_legend_style()
		# if obj and obj.sld_style:
		# 	return obj.sld_style
		#return None
		return obj

	def _generate_style(self):
		"""
		Generate SLD file for the layer

		See https://docs.geoserver.org/2.24.x/en/user/tutorials/cql/cql_tutorial.html
		See https://docs.geoserver.org/2.24.x/en/user/filter/ecql_reference.html#filter-ecql-reference
		"""  
		# enum_vals = [x.idx for x in self.legend_items]
		# sld = RasterStyle(style_name=self.style_name,
		# 				number_of_class=5,# 0, #len(enum_vals), # set 0 so that there are no ColorMapEntry
		# 				continuous_legend=True)#False)
		# style = sld.coverage_style(max_value=max(enum_vals),
		# 						   min_value=min(enum_vals))
		# style = style.replace('type="intervals"', 'type="values"')			

		# # replace the ColorMapEntry with the ones defined in the legend
		# entries = []
		# for itm in self.legend_items:
		# 	entries.append(f'<sld:ColorMapEntry color="{itm.color}" label="{itm.label}" quantity="{itm.expression}" opacity="3"/>')

		# # append nodata item style	
		# entries.append('<sld:ColorMapEntry color="#e95c47" label="Nodata" quantity="{0}" opacity="0"/>'.format(self.nodata))

		self.sld = style_from_legend(self.legend_name, self.legend_name, self.nodata, False, 0)
		
		# style.replace("</sld:ColorMap>", '\r\n'.join(entries) + '</sld:ColorMap>')	

		# self.sld = style.replace("</sld:ColorMap>", '<sld:ColorMapEntry color="#e95c47" label="Nodata" quantity="{0}" opacity="0"/>\n</sld:ColorMap>'.format(self.nodata))		
		
		# save sld file
		fl_name = self.save_style_to_disk(self.sld)
		# fl_name = "{0}.sld".format(self.style_name)
		# with open(fl_name, "w") as f:
		# 	f.write(self.sld)
		return fl_name
	
	def OLD_generate_style(self, raster_path):
		"""
		Generate SLD file for the layer

		See https://docs.geoserver.org/2.24.x/en/user/tutorials/cql/cql_tutorial.html
		See https://docs.geoserver.org/2.24.x/en/user/filter/ecql_reference.html#filter-ecql-reference
		"""  
		enum_vals = [x.idx for x in self.legend_items]
		sld = RasterStyle(style_name=self.style_name,
						number_of_class=5,# 0, #len(enum_vals), # set 0 so that there are no ColorMapEntry
						continuous_legend=True)#False)
		style = sld.coverage_style(max_value=max(enum_vals),
								   min_value=min(enum_vals))
		style = style.replace('type="intervals"', 'type="values"')			

		# replace the ColorMapEntry with the ones defined in the legend
		entries = []
		for itm in self.legend_items:
			entries.append(f'<sld:ColorMapEntry color="{itm.color}" label="{itm.label}" quantity="{itm.expression}" opacity="3"/>')

		# append nodata item style	
		entries.append('<sld:ColorMapEntry color="#e95c47" label="Nodata" quantity="{0}" opacity="0"/>'.format(self.nodata))

		self.sld = style.replace("</sld:ColorMap>", '\r\n'.join(entries) + '</sld:ColorMap>')	

		# self.sld = style.replace("</sld:ColorMap>", '<sld:ColorMapEntry color="#e95c47" label="Nodata" quantity="{0}" opacity="0"/>\n</sld:ColorMap>'.format(self.nodata))		
		
		# save sld file
		fl_name = self.save_style_to_disk(self.sld)
		# fl_name = "{0}.sld".format(self.style_name)
		# with open(fl_name, "w") as f:
		# 	f.write(self.sld)
		return fl_name

	def save_style_to_disk(self, style_xml):
		fl_name = "{0}.sld".format(self.style_name)
		with open(fl_name, "w") as f:
			f.write(style_xml)
		return fl_name

	def _generate_tile_url(self, raster_path):
		"""Generare WMS tile url

		Returns:
			string : Returns a tuple (url, layers) 
					e.g ('http://localhost:8600/geoserver/ldms/wms', 'ldms:modis_2000')'
		"""
		#setts = get_gis_settings() 
		# url = "{0}:{1}/{2}/wms".format(os.getenv('GEOSERVER_HOST', setts.backend_url).rstrip('/'), 
		# 							   os.getenv("GEOSERVER_PORT", 8600),
		# 							   self.workspace)
		url = "{0}/{1}/wms".format(self.public_url, self.workspace)
		head, tail = os.path.split(raster_path)
		raster_name = tail.split(".")[0]
		layers = "{0}:{1}".format(self.workspace, raster_name)
		return (url, layers)

	def publish_style(self, layer_name, workspace=None):
		"""Publish raster file to server

		Args:
			layer_name ([type]): [description]
			workspace ([type], optional): [description]. Defaults to None.
		"""
		res = self.geo.publish_style(layer_name=layer_name, 
				style_name=self.style_name, 
				workspace=workspace or self.workspace)
		return res


	def delete_workspace(self, workspace=None):
		"""Delete workspace

		Args:
			workspace (string): Workspace name. Defaults to the workspace name specified at init
		"""
		 # delete workspace
		res = self.geo.delete_workspace(workspace=workspace or self.workspace)
		# print("delete_workspace: ", res)
		# delete workspace if `workspace` is set or `workspace` is same as `self.workspace`
		if not workspace or workspace == self.workspace:
			self.workspace = None

	def delete_layer(self, layer, workspace=None):
		"""Delete layer from workspace

		Args:
			layer (string): Layer name
			workspace (string): Workspace name. Defaults to the workspace name specified at init
		"""
		res = self.geo.delete_layer(layer_name=layer, workspace=workspace or self.workspace)

	def get_legend_style(self):
		"""Get associated Published computation by enum type

		Args:
			change_enum (_type_): _description_
		"""
		# def _is_instance(enum_type):
		# 	for member in change_enum:
		# 		return isinstance(member, enum_type)
		# 	return False

		if self.legend_name:
			doc = frappe.get_doc("Legend", self.legend_name)
			return doc.sld_style
		return None
	