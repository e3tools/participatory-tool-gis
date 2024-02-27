import frappe
import re
import json
from gis.utils.common import extract_fields_from_formula, make_function
from gis.utils.raster import parse_raster, save_raster, return_raster_with_stats
from gis.utils.file import get_absolute_media_path
import fiona
import shapely
from shapely.geometry import shape
from frappe import _
import gis.defaults as DEFAULTS

class RasterAnalyzer:
	"""
	Raster File Analyzer wrapper
	"""
	def __init__(self, analysis_name=None, analysis_doc=None, vector=None):
		if not analysis_name and not analysis_doc:
			frappe.throw(_("Specify either the analysis name or the analysis document"))
		if analysis_doc:
			self.analysis_name = analysis_doc.analysis_name
			data_source = analysis_doc.data_source
		elif analysis_name:
			analysis_doc = frappe.get_doc("Technical Analysis", analysis_name)
			data_source = analysis_doc.data_source
			self.analysis_name = analysis_name
		 
		self.data_source = frappe.get_doc("Technical Data Source", data_source)
		self.raster_file = frappe.get_doc("Raster", self.data_source.raster)
		self.formula = analysis_doc.formula or 'x' #Formula for raster calculation are specified as x
		self.formula_regex = re.compile(r'{(.*?)}')
		self.vector = vector

	def _make_function(self):
		"""
		Construct a dynamic function based on the formula provided
		""" 
		# string_input = f"""def func(x):return {self.formula}""" 
		# exec(string_input)
		# return locals()['func']
		return make_function(self.formula)

	def analyze(self):
		"""
		Analyze a shapefile
		"""
		return self._analyze_pixel_values()

	def _analyze_pixel_values(self):
		"""
		Perform analysis for each pixel
		"""		
		raster_file = get_absolute_media_path(self.raster_file.raster_file)
		func = self._make_function()
		if self.formula.strip().lower() == 'x':
			# if formula is x, no need to apply a transform
			func = None
		out_raster, file_url, nodata, out_meta = parse_raster(raster_file, vector=self.vector, apply_func=func)
		# return (out_raster, file_url, nodata)
		
		# out_raster = df['mapping'].values.reshape(ilswe.shape)
		# out_raster = out_raster.astype(np.int32)
		resolution = self.raster_file.resolution
		return return_raster_with_stats(
			request=frappe.request,
			datasource=out_raster[0], 
			prefix=frappe.scrub(self.analysis_name), # prefix,
			legend_name=self.raster_file.legend, 
			metadata_raster_path=raster_file, #[x for x in clipped_raster_paths if x][0], #clipped_raster_paths[0], #clipped_rasters[0][1],
			nodata=nodata, 
			resolution=resolution,
			start_year=None,
			end_year=None,
			subdir=DEFAULTS.COMPUTED_RASTER_DIR, # ILSWESettings.SUB_DIR
			metadata=out_meta
		)
		