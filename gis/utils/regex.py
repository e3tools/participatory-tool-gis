import re

def match_between_strings(text, start_str, end_str):
    pattern = re.escape(start_str) + r'(.*?)' + re.escape(end_str)
    matches = re.findall(pattern, text, re.DOTALL)
    return matches