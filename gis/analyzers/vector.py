import frappe
import re
import json
from gis.utils.common import extract_fields_from_formula
import fiona
import shapely
from shapely.geometry import shape
from frappe import _

class ShapeFileAnalyzer:
    """
    Shape File Analyzer wrapper
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
        self.shape_file = frappe.get_doc("Shape File", self.data_source.shape_file)
        self.formula = analysis_doc.formula
        self.formula_regex = re.compile(r'{(.*?)}')
        self.START_DELIMITER = "{"
        self.END_DELIMITER = "}"

    def analyze(self):
        """
        Analyze a shapefile
        """
        return self._analyze_row_wise()

    def _analyze_row_wise(self):
        """
        Perform analysis for each row
        """
        def transform_row_keys(row):
            rc = frappe._dict()
            rc.geom = row.geom
            for attrb in self.shape_file.field_mappings:
                rc[attrb.attribute] = row.get(attrb.table_field)
            return rc

        parent_geojson = { "type": "FeatureCollection",
                "features": []
             }
        shape_file_items = self.shape_file.items
        rec = {
            self.analysis_name: None
        }
        rows = []
        for row in shape_file_items:
            # row = transform_row_keys(row)
            rec[self.analysis_name] = self._apply_formula(self.formula, row)
            row = transform_row_keys(row)
            row.update(rec)
            rows.append(row)

            parent_geojson["features"].append({'type': 'Feature', 
                                                'properties': json.loads(json.dumps(row)), 
                                                'geometry': json.loads(row.geom),
                                                'style_field': self.analysis_name
                                             })
        return rows, json.dumps(parent_geojson)

    def _analyze_column_wise(self):
        """
        Perform analysis for each column. This is especially the case for aggregate functions like COUNT, SUM, MEAN, STDDEV
        """
        pass

    def _apply_formula(self, formula, row):
        """
        Apply formula against a row
        """
        fields = extract_fields_from_formula(self.formula)
        for field in fields:
            attrib = field.lstrip(self.START_DELIMITER).rstrip(self.END_DELIMITER).strip()
            table_col = self._resolve_table_field(attrib)
            if table_col:
                formula = formula.replace(field, str(row.get(table_col))) #replace with row value

        # matches = []
        # # fields = self.formula_regex.findall(formula)
        # # retrieve the matched texts enclosed with {}
        # for match in self.formula_regex.finditer(formula):
        #     matches.append(match.group()) 

        # for match in matches:
        #     attrib = match.lstrip(self.START_DELIMITER).rstrip(self.END_DELIMITER).strip()
        #     table_col = self._resolve_table_field(attrib)
        #     if table_col:
        #         formula = formula.replace(match, str(row.get(table_col))) #replace with row value

        return frappe.safe_eval(formula)

    def _resolve_table_field(self, attribute):
        """
        Infer the table field given the attribute

        Data is stored in generic columns in the database but the user only knows of the attributes
        """
        mapping = [x for x in self.shape_file.field_mappings if x.attribute == attribute]
        return mapping[0].table_field if mapping else None
   