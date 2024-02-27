import frappe
import gis.defaults as DEFAULTS

class GISSettings:
    """
    Wrapper for GIS Settings
    """
    def __init__(self):
        pass
    
    @staticmethod
    def _get_settings():
        return frappe.db.get_singles_dict("GIS Settings") 
    
    @staticmethod
    def get_settings():
        """
        Get GIS Settings
        """
        return GISSettings._get_settings()
    
    
def get_gis_settings():
    return GISSettings.get_settings()