import re

FORMULA_REGEX = re.compile(r'{(.*?)}')
START_DELIMITER = "{"
END_DELIMITER = "}"

def extract_fields_from_formula(formula, return_enclosed=True):
	"""Extract fields included in formula and return them enclosed in curly braces

	Args:
		formula (_type_): _description_

	Returns:
		_type_: _description_
	"""
	matches = []
	fields = []
	# retrieve the matched texts enclosed with {}
	for match in FORMULA_REGEX.finditer(formula):
		matches.append(match.group()) 

	for match in matches:
		attrib = match if return_enclosed else match.lstrip(START_DELIMITER).rstrip(END_DELIMITER).strip()
		fields.append(attrib)
	return fields

def make_function(expression):
	"""
	Construct a dynamic function based on the formula provided
	""" 
	# replace x with x.val since x.val is the property of the Dataframe 
	string_input = f"""def func(x):return {expression}""" 
	exec(string_input)
	return locals()['func']