import frappe
from zipfile import ZipFile
from os.path import exists as f_exists
import tempfile
from frappe.utils import get_files_path
import os

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

def file_exists(file_path: str):
    """Does file exist

    Args:
        file_path (_type_): _description_
    """
    return f_exists(file_path)

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
