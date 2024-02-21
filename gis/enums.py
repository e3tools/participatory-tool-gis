import enum

class DatasetTypeEnum(enum.Enum):
    VECTOR = 'Vector'
    TABULAR = 'Table'
    RASTER = 'Raster' 

class RasterOperationEnum(enum.Enum):
	"""Enumeration for different raster operations
	"""
	ADD = 1
	SUBTRACT = 2
	DIVIDE = 3
	MULTIPLY = 4