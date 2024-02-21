import frappe
from zipfile import ZipFile
from os.path import exists as f_exists
import tempfile
from frappe.utils import get_files_path
import os
import time
import datetime

def unzip_file(zip_src: str, dest_dir=None):
	"""Unzip files

	Args:
		zip_src (str): Zip file
	"""
	zip_src = get_absolute_path(zip_src)
	files = []
	if file_exists(zip_src):
		if dest_dir:
			with ZipFile(zip_src) as zip:
				zip.extractall(path=dest_dir)
			files = [os.path.join(dest_dir, x) for x in os.listdir(dest_dir)] 
		else:
			with tempfile.TemporaryDirectory() as dest_dir:
				with ZipFile(zip_src) as zip:
					zip.extractall(path=dest_dir)
				files = [os.path.join(dest_dir, x) for x in os.listdir(dest_dir)] 
	return files

def file_exists(file_path: str, raise_exception=False):
	"""Does file exist

	Args:
		file_path (_type_): _description_
	"""
	exists = f_exists(file_path)
	# file = Path(file_path)
	# res = file.is_file()
	if raise_exception and not exists:
		raise FileNotFoundError("%s does not exist" % file_path) 
	return exists

def get_temp_file(suffix=".tif", prefix=None, delete=False):
	"""Generate a temp file"""
	return tempfile.NamedTemporaryFile(delete=delete, suffix=suffix, prefix=prefix).name

def get_absolute_path(file_path: str):
	"""
	Get File path

	If it is a relative file, it will infer the physical file location 
	""" 
	if(file_path.startswith('/files/')):
		file_path = f'{frappe.utils.get_bench_path()}/sites/{frappe.utils.get_site_base_path()[2:]}/public{file_path}'
	if(file_path.startswith('/private/')):
		file_path = f'{frappe.utils.get_bench_path()}/sites/{frappe.utils.get_site_base_path()[2:]}{file_path}'	 
	exists = file_exists(file_path)
	if exists:
		return file_path
	return None
 
def get_absolute_media_path(file_path=None, is_random_file=False, random_file_prefix=None, 
							random_file_ext=None, sub_dir=None, is_private=False):
	"""Get absolute file location given a relative file path
	   Also generates random file names and returns the absolute path
	Args:
		file_path (string): Relative file path
		is_random_file (bool): If True, a random file will be generated
		random_file_prefix (string): Prefix to pre-prepend the random file with
		random_file_ext (string): Extension of the random file to be generated
		sub_dir (string): Sub-directory within the parent directory

	Returns:
		string: A valid file location on file system
	"""
	# Validate
	# if not file_path and not is_random_file:
	# 	raise AnalysisParamError(_("Specify either a file_path or set is_random_file=True"))
	# elif file_path and is_random_file:
	# 	raise AnalysisParamError(_("File path cannot be specified when is_random_file=True"))
	
	if is_random_file:
		file_path = generate_file_name(prefix=random_file_prefix, extension=random_file_ext)
		path = get_media_dir(sub_dir, is_private=False) + file_path
	else: # validate that it is a valid path
		if file_exists(file_path, raise_exception=False):
			path = file_path
		else:
			path = get_media_dir(sub_dir, is_private=False) + file_path
	return path.replace("//", "/")


def get_media_dir(subdir=None, is_private=False):
	"""
	Return the directory path where media are stored

	Args:
		subdir (string): Sub-directory to append to directory
	"""
	root = None
	if not is_private:
		root = f'{frappe.utils.get_bench_path()}/sites/{frappe.utils.get_site_base_path()[2:]}/public'
	else: 
		root = f'{frappe.utils.get_bench_path()}/sites/{frappe.utils.get_site_base_path()[2:]}'	 
 
	path = root.rstrip("/") + "/"
	if subdir:
		path = "%s/%s/" % (root.rstrip("/"), subdir.rstrip("/"))
		path = path.replace("//", "/")
	return path

def generate_file_name(prefix=None, extension=None):
	"""Generate a file name based on timestamp"""
	return "%s%s%s" % ("" if not prefix else prefix, 
					 datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
					 "{}".format(extension) if extension else "")

def delete_temp_files(extension=None, age_in_seconds=0):
	"""Delete temp files

	Args:
		extension: File extension. Defaults to None.
		age_in_seconds (int, optional): Time since the file was created. For a day specify 86400. Defaults to 0.
	"""
	delete_files(tempfile.gettempdir(), extension=extension, age_in_seconds=age_in_seconds)

def delete_files(directory, extension=None, age_in_seconds=0):
	"""Delete files from a directory

	Args:
		directory: Directory containing the files
		extension: File extension. Defaults to None.
		age_in_seconds (int, optional): Time since the file was created. For a day specify 86400. Defaults to 0.
	"""
	now = time.time()
	for filename in os.listdir(directory):
		fname, fextn = os.path.splitext(filename)
		if extension and fextn != extension:
			continue
		# timestamp when the file contents were last modified
		file_full_path = os.path.join(directory, filename)
		if age_in_seconds:
			timestamp = os.stat(file_full_path).st_mtime
			reference_time = now - age_in_seconds
			if timestamp < reference_time: 
				os.remove(file_full_path)
		else:
			os.remove(file_full_path)