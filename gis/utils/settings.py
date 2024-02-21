import frappe
import gis.defaults as DEFAULTS

class GISSettings:
    """
    Wrapper for GIS Settings
    """
    def __init__(self):
        pass
    
    def _get_settings(self):
        return frappe.db.get_singles_dict("GIS Settings")

    @staticmethod
    @property
    def DEFAULT_NODATA():
        settings = GISSettings._get_settings().default_nodata or DEFAULTS.NODATA

    @staticmethod
    @property
    def MIN_INT():
        return -9223372036854775807

    @staticmethod
    @property
    def MAX_INT():
        return 9223372036854775807 
    
    @staticmethod
    def get_settings():
        """
        Get GIS Settings
        """
        return GISSettings._get_settings()
    
    
def get_gis_settings():
    return GISSettings.get_settings()