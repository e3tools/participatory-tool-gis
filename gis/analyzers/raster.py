import frappe
import re
import json
from gis.utils.common import extract_fields_from_formula
from gis.utils.raster import parse_raster, save_raster
from gis.utils.file import get_absolute_media_path
import fiona
import shapely
from shapely.geometry import shape
from frappe import _

class RasterFileAnalyzer:
    """
    Raster File Analyzer wrapper
    """
    def __init__(self, analysis_name=None, analysis_doc=None):
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
        # self.START_DELIMITER = "{"
        # self.END_DELIMITER = "}"

    def _make_function(self):
        """
        Construct a dynamic function based on the formula provided
        """
        # def func(x):
        #     return frappe.safe_eval(self.formula)
        # return func
        string_input = f"""
            def func(x):
                return {self.formula}
            """
        return eval(string_input)  

    def analyze(self):
        """
        Analyze a shapefile
        """
        return self._analyze_pixel_values()

    def _analyze_pixel_values(self):
        """
        Perform analysis for each pixel
        """
        def transform_row_keys(row):
            rc = frappe._dict()
            rc.geom = row.geom
            for attrb in self.shape_file.field_mappings:
                rc[attrb.attribute] = row.get(attrb.table_field)
            return rc
        
        raster_file = get_absolute_media_path(self.raster_file.raster_file) 
        out_raster, file_url, nodata = parse_raster(raster_file, vector=None, apply_func=self._make_function())
        return (out_raster, file_url, nodata)