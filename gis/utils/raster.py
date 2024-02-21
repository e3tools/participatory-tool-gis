import frappe
import rasterio 
from gis.utils.file import get_absolute_media_path, file_exists, get_temp_file, delete_temp_files
from gis.utils.settings import GISSettings, get_gis_settings
#from gis.utils.geoserver import GeoServerHelper
import gis.defaults as DEFAULTS
import json
import numpy as np
from frappe.utils import cint
from frappe.utils.file_manager import save_file_on_filesystem
import datetime
from gis.enums import RasterOperationEnum

# see https://geoscripting-wur.github.io/PythonRaster/

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

def get_raster_meta(rasterfile, set_default_nodata=True, default_nodata=GISSettings.DEFAULT_NODATA):
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
		if not (GISSettings.MIN_INT <= nodataval <= GISSettings.MAX_INT):
			meta.update({'nodata': default_nodata})
		elif isinstance(nodataval, float):
			meta.update({'nodata': default_nodata})

	return meta

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
	# read the file and crop areas outside the polygon
	if vector:
		with rasterio.open(file) as src:
			nodata = dest_nodata if dest_nodata != None else src.meta['nodata'] or DEFAULTS.NODATA
			out_image, out_transform = rasterio.mask.mask(src, 
						[json.loads(vector)], # accepts array of shapes
						all_touched=all_touched,
						nodata=nodata,
						crop=True)
			out_meta = src.meta

					# update meta
			out_meta.update({
				"driver": "GTiff",
				"height": out_image.shape[1],
				"width": out_image.shape[2],
				"transform": out_transform
			})
	else:
		# if no vector specified, nothing to crop, so return full raster
		with rasterio.open(file) as src:
			nodata = dest_nodata if dest_nodata != None else src.meta['nodata'] or DEFAULTS.NODATA
			out_image = src.read(1) # src.copy()
			out_image[out_image==nodata] = np.ma.masked
			out_image[np.isnan(out_image)] = np.ma.masked
			out_meta = src.meta
	
			# update meta
			out_meta.update({
				"driver": "GTiff",
				"height": out_image.shape[0],
				"width": out_image.shape[1],
				# "transform": out_transform
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
		out_file = get_temp_file(suffix=".tif")
	else:
		out_file = get_absolute_media_path(file_path=None, 
									is_random_file=True, 
									random_file_prefix="",
									random_file_ext=".tif")
									
	with rasterio.open(out_file, "w", **out_meta) as dest:
		dest.write(out_image)

	# save to frappe site files folder
	with open (out_file, "rb") as myfile:
		data_file=myfile.read()

	frappe.db.connect() #connect incase just to avoid risk of Lost connection error
	#delete_file("files/" + report_name + ".zip") # delete old zip if it exists
	
	output_raster_path = str(datetime.datetime.now()).replace(' ', '_').replace('-','').replace(':','').replace('.', '_') + '.png'# '.tif'
	fl = save_file_on_filesystem(output_raster_path, content=data_file)

	# return (out_image, out_file, out_meta['nodata'])
	return (out_image, fl['file_url'], out_meta['nodata'])

def return_raster_with_stats(request, datasource, prefix, change_enum, 
							   metadata_raster_path, nodata, resolution,
							   start_year, end_year, subdir=None, results=None,
							   extras={}, is_intermediate_variable=False, 
							   precomputed_field_map={}):
	"""Generates a raster and computes the statistics

	Args:
		request (request): Http Request
		datasource (array): Raster array to save
		prefix (string): Name to prefix the generated raster with
		change_enum (enum.Enum): Type of Enumeration for different changes 
								e.g ProductivityChangeTernaryEnum, TrajectoryChangeTernaryEnum
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
					statistics categorized by the change_enum 
	"""
	# TODO validate change_enum
	# if type(change_enum) not in [StateChangeTernaryEnum, PerformanceChangeBinaryEnum, ProductivityChangeTernaryEnum]:
	# 	raise AnalysisParamError(_("The change enum source specified is invalid. Ensure it is a valid enumeration"))
	
	delete_temp_files(extension=".tif", age_in_seconds=DEFAULTS.DELETE_TEMP_FILES_AFTER or 86400)

	out_file = get_absolute_media_path(file_path=None, 
									is_random_file=True, 
									random_file_prefix=prefix,
									random_file_ext=".tif",
									sub_dir=subdir,
									is_private=False)

	raster_file = save_raster(dataset=datasource, 
							  source_path=metadata_raster_path,
							  target_path=out_file)
	
	raster_url = "%s" % (get_download_url(request, raster_file, 
										  is_private=False))
	results = results or []		
	
	# Get counts of change types		
	# unique, counts = np.unique(datasource[datasource != nodata], return_counts=True)			
	unique, counts = np.unique(datasource, return_counts=True)			
	val_counts = dict(zip(unique, counts)) # convert to {val:count} freq distribution dictionary
	
	if not results:
		for mapping in change_enum:
			key = cint(mapping.key)
			if key in val_counts:
				val = val_counts[mapping.key]
				results.append({
					'change_type': key,
					'label': str(mapping.label),
					'count': val,
					'area': compute_area(val, resolution)
				})
			else:
				results.append({
					'change_type': key,
					'label': str(mapping.label),
					'count': 0,
					'area': 0
				})

	nodata_count = 0 
	if nodata in val_counts:
		nodata_count = val_counts[nodata]

	wms_url, layer = None, None
	if not is_intermediate_variable and get_gis_settings().enable_tiles:
		wms_url, layer = generate_tiles(raster_file=out_file, nodata=nodata, change_enum=change_enum)

	stats_obj = {
			# "baseline": "{}-{}".format(baseline_period[0], baseline_period[-1]),
			"base": start_year,
			"target": end_year,
			"rasterfile": raster_url,
			"rasterpath": raster_file,
			"precomputed_field_map": precomputed_field_map,
			"nodataval": nodata,
			"nodata": compute_area(nodata_count, resolution),
			'stats': results,
			'extras': extras,
			'change_enum': str(change_enum),
			'tiles': {
				'url': wms_url,
				'layer': layer
			}
		} 
	return stats_obj

def save_raster(dataset, source_path, target_path, dtype=rasterio.int16, no_data=None):	
	"""
	Write raster dataset to disk

	Args:
		source_path (string): Path of raster where we will get the Metadata
		target_path (string): Path to save the raster
	"""
	rasterin = get_absolute_media_path(source_path.replace("//", "/"), is_private=False)
	rasterout = target_path.replace("//", "/")
 
	# open source to extract meta
	meta = get_raster_meta(rasterin) 
	meta.update({
				 'dtype': dtype, # rasterio.uint8,
				 'compress': 'lzw',
				 'height': dataset.shape[0],
				 'width': dataset.shape[1],				 
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
	return target_path.split("/")[-1]

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

def generate_tiles(raster_file, nodata, change_enum):
	"""Generate Tiles

	Args:
		raster_file (string): Raster file
		nodata (number): Nodata value
		change_enum (enum.Enum): Type of Enumeration for different changes 
								e.g ProductivityChangeTernaryEnum, TrajectoryChangeTernaryEnum
	Returns:
		Returns a WMS url
	""" 	
	geo = GeoServerHelper(analysis_enum=change_enum, nodata=nodata)
	return geo.upload_raster(raster_file) 
