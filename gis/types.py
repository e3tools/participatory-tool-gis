class StrippedRaster:
    """
    Class to hold stripped version of Raster for computation
    """
    def __init__(self, id, name, raster_file, resolution):
        self.id = id
        self.name = name
        self.raster_file = raster_file
        self.resolution = resolution

    @property
    def id(self):
        return self.id
    
    @property
    def name(self):
        return self.name
    
    @property
    def raster_file(self):
        return self.raster_file
    
    @property
    def resolution(self):
        return self.resolution