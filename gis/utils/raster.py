import frappe
import rasterio 
import rasterio.mask
from gis.utils.file import get_absolute_media_path, file_exists, get_temp_file, delete_temp_files, create_folder
from gis.utils.settings import GISSettings, get_gis_settings
from gis.utils.geoserver import GeoServerHelper
import gis.defaults as DEFAULTS
import json
import numpy as np
from frappe.utils import cint, get_files_path
from frappe.utils.file_manager import save_file_on_filesystem
import datetime
from gis.enums import RasterOperationEnum
import os
import rasterstats
import geopandas as gpd
from gis.types import StrippedRaster
import pandas as pd
from gis.utils.common import make_function
import re
import swifter


# see https://geoscripting-wur.github.io/PythonRaster/
# See https://community.esri.com/t5/python-snippets-blog/calculating-zonal-statistics-with-python/ba-p/883278

class RasterCalcHelper():   
	"""
	Helper Class to compute Raster statistics using vector geometries

	Call `get_stats` method to get computed statistics

	Referenced as `RasterCalcHelper().get_stats()`
	
	# TODO: validate the Geometry passed
	# TODO: Optimize for large images
	# TODO: Test that raster extent falls within the vector. Check https://www.earthdatascience.org/courses/use-data-open-source-python/spatial-data-applications/lidar-remote-sensing-uncertainty/extract-data-from-raster/
	"""

	def __init__(self, 
				vector, 
				rasters, 
				raster_type_id, 
				stats=None, 
				is_categorical=True, 
				transform="x",                
				raster_resolution=None):
		"""
		Initialize instance values
		
		Args:
			shapefile:
				Vector data to use to overlay raster on. Either of: 
					- Shapefile path 
					- Geometry either of ["Point", "LineString", "Polygon",
						"MultiPoint", "MultiLineString", "MultiPolygon"]
			rasters (list<StrippedRaster>): 
				List of lists of the form list<StrippedRaster>
			
			raster_type_id (int):
				Id of the raster types that are being processed

			is_categorical (bool):
				If True, the output of zonal_stats is dictionary with the unique raster values 
				as keys and pixel counts as values

			transform (string):
				Either of:
					- "area"
					- a string with placeholder e.g x * x to mean square of that value
			
			raster_resolution [Deprecated]:
				Resolution of the raster as explicity value if `raster` is set as a path to
				a raster file. If `raster` is set as a reference to a Raster model, the 
				resolution is retrieved from the raster metadata
		"""
		self.vector = vector
		self.rasters = rasters
		self.stats = ['mean']
		self.categorical = is_categorical
		self.raster_band_stats = [] #computed results per rasterband
		# self.raster_resolution = 30 # Resolution of the raster
		self.raster_type_id = raster_type_id # Raster type id
		self.value_placeholder = "x" #placeholder for value in transform equation
		self.transform = transform or self.value_placeholder # how to transform generated stats
		
		# if its categorical, we will just return the count per each category of values
		if is_categorical == True: 
			self.stats = []

	def get_stats(self):
		"""[summary]
		Because we are interested with the count of individual
		pixel values, we pass the categorical=True parameter
		to force the function to get us results as a dict 
		of the form {1.0: 1, 2.0: 9, 5.0: 40}

		As per the documentation:
		"You can treat rasters as categorical (i.e. raster values represent 
		discrete classes) if you’re only interested in the counts of unique pixel values."

		As per the documentation:
		"Using categorical, the output 
		is dictionary with the unique raster 
		values as keys and pixel counts as values:"

		Returns:
			List of stats for each rasterband.
			   
		"""
		# TODO: Retrieve the value of shapefile depending on what has been passed
		# TODO: Retrieve the value of raster and the mapping if necessary

		vectors = self.vector
		if self.is_vector_a_path():
			gdf = gpd.read_file(self.vector)
			vectors = gdf['geometry']

		stats_obj = {
			"mapping": self.get_raster_value_mapping(self.raster_type_id),
			'stats': []         
		}

		for raster in self.rasters:
			results = []
			raster_path = get_absolute_media_path(raster.raster_file)   
			clipped_raster, ndata, rastfile, out_meta = clip_raster_to_vector(raster_path, vectors)

			# self.raster_band_stats = rasterstats.zonal_stats(vectors=vectors,
			# 				raster=raster_path,
			# 				categorical=self.categorical) #[1]
			self.raster_band_stats = rasterstats.zonal_stats(vectors=vectors,
							raster=rastfile,
							categorical=self.categorical) #[1]
			
			meta_data = self.get_raster_metadata(raster.id)

			mapping = meta_data['mapping']# self.get_raster_value_mapping(raster.id)
			resolution = meta_data['resolution']
			
			if self.categorical: 
				# we are only getting counts for each unique pixel value for categorical data            
				for layer_stats in self.raster_band_stats: # Loop through the results of each band
					for key in layer_stats.keys():
						if mapping:
							mp = [x for x in mapping if key==x['id']]
							if mp:
								val = layer_stats[key]
								results.append({ 
									"key": key, 
									"label": str(mp[0]['label']),
									"raw_val": val,
									"value": self.transform_value(val, raster.id, resolution), 
								})
						else:								
							val = layer_stats[key]
							results.append({ 
								"key": key, 
								"label": str(key),
								"raw_val": val,
								"value": self.transform_value(val, raster.id, resolution),
							})
			else:
				results = self.raster_band_stats
			
			stats_obj['stats'].append({
				"raster_id": meta_data['raster'],
				"raster_name": raster.name,
				"resolution": meta_data['resolution'],
				'year': meta_data['year'],    
				'stats': results,
			})
		return stats_obj

	def append_metadata(self, results, raster_id):
		"""
		Append Raster metadata to the results

		Args:
			results:
				Results generated from the computations
		"""
		meta_data = self.get_raster_metadata(raster_id)
		return {
			"meta": {
				"raster": meta_data['raster'],
				"resolution": meta_data['resolution'],
				"mapping": meta_data['mapping'],                
			},
			"stats": [{
					'year': meta_data['year'],
					'values': results
				}] 
		}

	def transform_value(self, val, raster_id, raster_resolution=None):
		"""
		Transforms the raster band stat results.
		E.g you can calculate the area covered given the pixel count
		"""
		if self.transform == "area":
			resolution = raster_resolution or self.retrieve_raster_resolution(raster_id)
			# return resolution * resolution * val # multiply resolution squared by pixel count
			return compute_area(val, resolution)
		else:
			return eval(self.transform.replace(self.value_placeholder, str(val)))
	
	def is_vector_a_path(self):
		"""
		Checks if the supplied `shapefile` parameter is a path to a file
		"""
		if self.vector.endswith(".shp"):
			return file_exists(self.vector, raise_exception=False)
		return False
 
	def get_raster_metadata(self, raster_id):
		"""
		Retrieves Raster metadata as stored in the database.

		Args:
			raster_id:
				ID of raster to retrieve metadata for

		Returns:
			Dictionary with the keys:
				`raster`: Name of the raster
				`resolution`: Resolution of the raster
				`mapping`: A dictionary of pixel value with the corresponding label
						E.g {1: "Forest", 2: "Grassland"}  
		"""
		doc = frappe.get_doc("Raster", raster_id)
		mapping = {}
		# if doc.raster_type:
		# 	mapping = [{"id": x.id, "val": x.value, "label": x.label, "color": x.color} for x in doc.raster_type.rastervaluemapping_set.all()]

		meta = {
				"raster": doc.id,
				"resolution": doc.resolution or 1,
				"year": doc.raster_year,
				"mapping": mapping,               
			}
		return meta

	def retrieve_raster_resolution(self, raster_id):
		"""
		Retrieve the resolution of a raster from its stored metadata in 
		the Raster model        
		"""
		meta = self.get_raster_metadata(raster_id)
		return meta['resolution']

	def get_raster_legend(self, legend_id):
		"""
		Get a mapping of raster value with the corresponding label
		E.g {1: "Forest", 2: "Grassland"}

		Args:
			raster_type_id:
				Id of the raster type to retrieve metadata for
		"""
		doc = frappe.get_doc("Legend", legend_id)
		mapping = [{"id": x.id, "val": x.value, "label": x.label, "color": x.color} for x in model.rastervaluemapping_set.all()]
		return mapping
	
def parse_raster(file_path: str, vector=None, apply_func=None):
	"""Read the contents of a raster file

	Args:
		file_path (string): File Path
		vector (string): Vector to clip
		apply_func (function): Function to be applied to each pixel value
	"""
	return clip_raster_to_vector(raster_file=file_path, vector=vector, apply_func=apply_func)

def get_meta_data(file_path):
	"""Get metadata
	Args:
		file_path (string): File path
	"""
	pass

def get_raster_meta(rasterfile, set_default_nodata=True, default_nodata=DEFAULTS.NODATA):
	"""
	Get RasterFile metadata
	"""
	rasterin = get_absolute_media_path(rasterfile)
	with rasterio.open(rasterin) as src:
 		meta = src.meta
	
	if set_default_nodata:
		if 'nodata' not in src.meta or src.meta.get('nodata', None) == None:
			meta.update({'nodata': default_nodata})
		# if nodatavalue not within int range, set to default value
		nodataval = meta['nodata']
		if not (DEFAULTS.MIN_INT <= nodataval <= DEFAULTS.MAX_INT):
			meta.update({'nodata': default_nodata})
		elif isinstance(nodataval, float):
			meta.update({'nodata': default_nodata})

	return meta

def get_drivers():
	# comment out JPEG since JPEG only supports int8 and int12
	# if DEFAULTS.COMPUTED_RASTER_FILE_TYPE in [".jpeg", ".jpg"]:
	# 	return "JPEG"
	if DEFAULTS.COMPUTED_RASTER_FILE_TYPE == ".png":
		return "PNG"
	if DEFAULTS.COMPUTED_RASTER_FILE_TYPE in [".tiff", ".tif"]:
		return "GTiff"
	return "PNG"

def clip_raster_to_vector(raster_file, vector=None, use_temp_dir=True, dest_nodata=None, apply_func=None):
	"""
	Mask out regions of a raster that are outside the polygons defined in the shapefile.

	Args:
		vector (geojson): Polygon to be used for clipping
		dest_nodata (number): Value to set as nodata when returning the clipped raster
		apply_func (function): Function to be applied to each pixel value
	
	Returns (string, array): Tuple of Url of the clipped raster and the raster array
	"""
	file = get_absolute_media_path(raster_file)
	if not file_exists(file):
		return (None, None)
		
	all_touched = GISSettings.get_settings().raster_clipping_algorithm == "All Touched"
	out_meta = {}
	# read the file and crop areas outside the polygon 
	with rasterio.open(file) as src:
		out_meta = src.meta
		nodata = dest_nodata if dest_nodata != None else src.meta['nodata'] or DEFAULTS.NODATA
		if vector:
			shapes = [x['geometry'] for x in json.loads(vector)['features']]
			out_image, out_transform = rasterio.mask.mask(src, 
						shapes, #[json.loads(vector)], # accepts array of shapes
						all_touched=all_touched,
						nodata=nodata,
						crop=True)
			# update meta
			out_meta.update({ 
				"transform": out_transform
			})
		else:
			out_image = src.read() 

	# convert to maskedArray
	out_image = np.ma.MaskedArray(out_image)

	if 'int' in out_meta['dtype']:
		nodata = cint(nodata)
	out_image[out_image==nodata] = np.ma.masked
	out_image[np.isnan(out_image)] = np.ma.masked

	# update meta
	out_meta.update({
		"driver": get_drivers(), #"GTiff",
		"height": out_image.shape[1],
		"width": out_image.shape[2], 
	}) 

	# enable compress
	out_meta.update({'compress': 'lzw'})

	# update nodata
	out_meta.update({'nodata': nodata})

	if apply_func:
		# see https://blog.enterprisedna.co/how-to-map-a-function-over-numpy-array/
		res = np.array(list(map(apply_func, out_image)))
		out_image = res

	# get output file
	if use_temp_dir:
		out_file = get_temp_file(suffix=DEFAULTS.COMPUTED_RASTER_FILE_TYPE)
	else:
		out_file = get_absolute_media_path(file_path=None, 
									is_random_file=True, 
									random_file_prefix="",
									random_file_ext=DEFAULTS.COMPUTED_RASTER_FILE_TYPE)
									
	with rasterio.open(out_file, "w", **out_meta) as dest:
		dest.write(out_image)

	# save to frappe site files folder
	with open (out_file, "rb") as myfile:
		data_file=myfile.read()

	frappe.db.connect() #connect incase just to avoid risk of Lost connection error
	# #delete_file("files/" + report_name + ".zip") # delete old zip if it exists
	
	# convert back to normal array from maskedArray
	out_image = np.array(out_image)
	return (out_image, out_file, out_meta['nodata'], out_meta)
	# extension = DEFAULTS.COMPUTED_RASTER_FILE_TYPE or '.png'

	# analysis_sub_folder = DEFAULTS.COMPUTED_RASTER_DIR or 'analysis/rasters'
	# folder = os.path.join(get_files_path(is_private=False), analysis_sub_folder)
	# create_folder(folder)

	# output_raster_file = str(datetime.datetime.now()).replace(' ', '_').replace('-','').replace(':','').replace('.', '_') + extension
	# file_path = os.path.join(analysis_sub_folder, output_raster_file)
	# fl = save_file_on_filesystem(file_path, content=data_file)

	
	# return (out_image, fl['file_url'], out_meta['nodata'])

def return_raster_with_stats(request, datasource, prefix, legend_name, 
							   metadata_raster_path, nodata, resolution,
							   start_year, end_year, subdir=None, results=None,
							   extras={}, is_intermediate_variable=False, 
							   precomputed_field_map={}, metadata={}):
	"""Generates a raster and computes the statistics

	Args:
		request (request): Http Request
		datasource (array): Raster array to save
		prefix (string): Name to prefix the generated raster with
		legend_name (string): Type of Enumeration for different changes. The Legend for the analysis
		metadata_raster_path (string): Path of the raster where to get Metadata from
		nodata (int): Value of nodata
		resolution (int): Resolution to use to compute statistics
		subdir (string): Name of sub directory to save the raster
		results (object): An object already containing calculated values
		extras (dict): Extra key value object that you may want to return in addition to std values
		is_intermediate_variable: True if the results are to be used as an intermediate value not the final value
		precomputed_field_map: Dict of how extra values of statistics will be stored. An example is ForestChange and LULC which has additional values for the results

	Returns:
		object : An object with url to download the generated raster and
					statistics categorized by the legend 
	""" 

	def _make_function(expression):
		"""
		Construct a dynamic function based on the formula provided
		""" 
		# replace x with x.val since x.val is the property of the Dataframe 
		# string_input = f"""def func(x):return {expression}""" 
		# exec(string_input)
		# return locals()['func']
		return make_function(expression)
	
	delete_temp_files(extension=DEFAULTS.COMPUTED_RASTER_FILE_TYPE, age_in_seconds=DEFAULTS.DELETE_TEMP_FILES_AFTER or 86400)

	out_file = get_absolute_media_path(file_path=None, 
									is_random_file=True, 
									random_file_prefix=prefix,
									random_file_ext=DEFAULTS.COMPUTED_RASTER_FILE_TYPE,
									sub_dir=subdir,
									is_private=False)
	
	tmp_file = get_temp_file()

	raster_file = save_raster(dataset=datasource, 
							  source_path=metadata_raster_path,
							  target_path=tmp_file,
							  metadata=metadata)
	
	# save to frappe site files folder
	fl = save_to_frappe_sites_folder(src_path=raster_file, dest_path=os.path.split(out_file)[-1]) 

	raster_url = fl['file_url'] #"%s" % (get_download_url(request, raster_file, is_private=False))
	results = results or []		
	
	# Get counts of change types		
	# unique, counts = np.unique(datasource[datasource != nodata], return_counts=True)			
	unique, counts = np.unique(datasource, return_counts=True)			
	val_counts = dict(zip(unique, counts)) # convert to {val:count} freq distribution dictionary

	# Evaluate legend items
	legend = frappe.get_doc("Legend", legend_name)

	df = pd.DataFrame({
						'val': datasource.flatten(), # datasource.filled(fill_value=nodata).flatten(),												
					})
	df['label'] = 'Uncategorized'
	nodata_mask = (df['val'] == nodata)
	if not results:
		#for mapping in change_enum:
		for mapping in legend.legend_entries:
			#df.loc[df.apply(lambda x: (x.val % 2 == 0), axis=1 ) ,  'mapping'] = 11

			
			# func = _make_function(expression)
			# if expression.strip().lower() == 'x':
			# 	# if formula is x, no need to apply a transform
			# 	func = None			
			# 	mask = (df['val'] != nodata) & (df['val'] != mapping.) & (df['lulc'] != nodata)
			# 	df.loc[~nodata_mask & mask, ['label']] = mapping.label
			# else:
			
			# replace x with x.val since x.val is the property of the Dataframe
			# expression = mapping.expression.replace('x', 'x.val')
			expression = mapping.expression
			# df.loc[df.apply(_make_function(expression), axis=1), ['label']] = mapping.label
			func = _make_function(expression)
			df['label'] = df['val'].swifter.apply(func)

			count = df[df.label == mapping.label].shape[0]

			results.append({
				'change_type': mapping.label,
				'label': str(mapping.label),
				'color': str(mapping.color),
				'expression': str(mapping.expression),
				'count': count,
				'area': compute_area(count, resolution)
			}) 

	nodata_count = 0 
	if nodata in val_counts:
		nodata_count = val_counts[nodata]

	wms_url, layer = None, None
	if not is_intermediate_variable and cint(get_gis_settings().enable_tiles):
		wms_url, layer = generate_tiles(raster_file=out_file, nodata=nodata, legend_name=legend_name)

	stats_obj = {
			# "baseline": "{}-{}".format(baseline_period[0], baseline_period[-1]),
			"base": start_year,
			"target": end_year,
			"rasterfile": raster_url,
			"rasterpath": raster_url, # raster_file,
			"precomputed_field_map": precomputed_field_map,
			"nodataval": nodata,
			"nodata": compute_area(nodata_count, resolution),
			'stats': results,
			'extras': extras,
			'change_enum': str(legend_name),
			'tiles': {
				'url': wms_url,
				'layer': layer
			}
		} 
	return stats_obj

def sanitize_expression(expression):
	"""
	Sanitize expression by replacing operators 
	"""
	#[x.group() for x in re.compile(r'[\+|-|\*|\/|=|>|<|>=|<=|&|\||%|\!|\^]').finditer(txt)]

	pass

def save_to_frappe_sites_folder(src_path, dest_path):
	# save to frappe site files folder
	with open (src_path, "rb") as myfile:
		data_file=myfile.read()

	frappe.db.connect() #connect incase just to avoid risk of Lost connection error
	
	extension = DEFAULTS.COMPUTED_RASTER_FILE_TYPE or '.png'

	analysis_sub_folder = DEFAULTS.COMPUTED_RASTER_DIR or 'analysis/rasters'
	folder = os.path.join(get_files_path(is_private=False), analysis_sub_folder)
	create_folder(folder)

	output_raster_file = dest_path # str(datetime.datetime.now()).replace(' ', '_').replace('-','').replace(':','').replace('.', '_') + extension
	file_path = os.path.join(analysis_sub_folder, output_raster_file)
	fl = save_file_on_filesystem(file_path, content=data_file)
	return fl

def save_raster(dataset, source_path, target_path, dtype=rasterio.uint16, no_data=None, metadata={}):	
	"""
	Write raster dataset to disk

	Args:
		source_path (string): Path of raster where we will get the Metadata
		target_path (string): Path to save the raster
	"""
	rasterin = get_absolute_media_path(source_path.replace("//", "/"), is_private=False)
	rasterout = target_path.replace("//", "/")
 
	# open source to extract meta
	meta = get_raster_meta(rasterin) if not metadata else metadata
	meta.update({
				 'dtype': dtype, # rasterio.uint8,
				 'compress': 'lzw',
				 'height': dataset.shape[0],
				 'width': dataset.shape[1],		
				 "driver": get_drivers(), #"GTiff",		 
				})	
	if no_data:
		meta.update({
			"nodata": no_data
		})
	nodata = override_nodata(meta['nodata'])
	meta.update({"nodata": nodata})
	with rasterio.open(rasterout, 'w', **meta) as dst:		
		# dst.write(dataset.astype(rasterio.uint8), 1)
		if len(dataset.shape) == 2:
			dst.write(dataset.astype(dtype), 1)
		else:
			dst.write(dataset.astype(dtype))
		
	"""
	bands = [x + 1 for x in list(range(rast.count))]
	rast.close()
	badbands = [7, 16, 25]

	nodatavalue = 255
	with rasterio.open(rasterout, 'w', **meta) as dst:
		with rasterio.open(rasterin) as src:
			for ID, b in enumerate(bands,1):
				# if b in ndvibands:
				# 	ndvi = src.read(b)
				# 	ndvi[ndvi != 0] = 0
				# 	dst.write(ndvi, ID)
				# else:
				data = src.read(b, masked=True)
				data = np.ma.filled(data, fill_value=nodatavalue)
				#data[data == 2] = 0
				dst.write(data, ID)
	dst.close
	"""
	return target_path # target_path.split("/")[-1]

def override_nodata(nodata):
	"""Harmonize nodata value
	If nodata value not between np.int8 range, return the default value
	"""
	#if not (settings.MIN_INT <= nodataval <= settings.MAX_INT):
	info = np.iinfo(np.int16)
	if info.min <= nodata <= info.max:
		return nodata
	return DEFAULTS.NODATA

def compute_area(pixel_count, resolution):
	"""
	Get the area given pixel count and resolution

	Args:
		pixel_count (int): _description_
		resolution (int): _description_

	Returns:
		Area
	"""
	# The area is arrived at getting the area per pixel multiplied by number of pixels
	return (resolution or 1) * (resolution or 1) * pixel_count # multiply resolution squared by pixel count

def do_raster_operation(rasters, operation: RasterOperationEnum, nodata):
	"""
	Perform operations on rasters

	Args:
		rasters (list): List of rasters
		operation (RasterOperationEnum): Type of operation
	"""
	res = None
	if isinstance(rasters, list):
		if operation == RasterOperationEnum.DIVIDE and len(rasters) != 2:
			frappe.throw(_("The list must contain only 2 arrays"))
		
		masked_arrays = []
		# mask nodata values
		for i, itm in enumerate(rasters):
			# loop because np.ma.<arithmetic> replaces the masked values
			itm = np.ma.array(itm, fill_value=nodata)
			itm[itm==nodata] = np.ma.masked # mask no data
			itm[np.isnan(itm)] = np.ma.masked # mask non-numerics
			masked_arrays.append(itm)

			if i == 0:
				res = itm
			else:
				if operation == RasterOperationEnum.ADD:
					res = np.ma.add(res, itm)
				elif operation == RasterOperationEnum.SUBTRACT:
					res = np.ma.subtract(res, itm)
				elif operation == RasterOperationEnum.MULTIPLY:
					res = np.ma.multiply(res, itm)
				elif operation == RasterOperationEnum.DIVIDE:
					res = np.ma.divide(res, itm)
	return res

def generate_tiles(raster_file, nodata, legend_name):
	"""Generate Tiles

	Args:
		raster_file (string): Raster file
		nodata (number): Nodata value
		legend_name (): Legend for Enumeration for different changes  
	Returns:
		Returns a WMS url
	""" 	
	geo = GeoServerHelper(legend_name=legend_name, nodata=nodata)
	return geo.upload_raster(raster_file) 
