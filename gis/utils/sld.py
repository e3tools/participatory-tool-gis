import frappe
from pysld.style import RasterStyle#, Style 
import re
from gis.utils.regex import match_between_strings

def style_from_legend(legend, style_name, nodata, continuous=False, num_classes=0):
    """Generate SLD layer from Legend

    Args:
        legend: Name of the legend
        style_name: Name of style
        nodata: value of nodata
        continuous (bool, optional): Is the style continous. Defaults to False.
        num_classes (int, optional): Number of classes to be generated. Defaults to 0.

    Returns:
        Generated SLD layer
    """
    doc = frappe.get_doc("Legend", legend)
    if not continuous:
        num_classes = len(doc.legend_items)
    enum_vals = [x.idx for x in doc.legend_items]
    sld = RasterStyle(style_name=style_name,
                    number_of_class=num_classes, #5,# 0, #len(enum_vals), # set 0 so that there are no ColorMapEntry
                    continuous_legend=continuous)#False)
    style = sld.coverage_style(max_value=max(enum_vals),
                                min_value=min(enum_vals))
    style = style.replace('type="intervals"', 'type="values"')			

    # replace the ColorMapEntry with the ones defined in the legend
    entries = []
    for itm in doc.legend_items:
        entries.append(f'<sld:ColorMapEntry color="{itm.color}" label="{itm.label}" quantity="{itm.expression}" opacity="3"/>')

    # append nodata item style	
    entries.append('<sld:ColorMapEntry color="#e95c47" label="Nodata" quantity="{0}" opacity="0"/>'.format(nodata))

    return style.replace("</sld:ColorMap>", '\r\n'.join(entries) + '</sld:ColorMap>')

def legend_from_sld(sld):
    """
    Extract Legend from SLD 
    """
    def _extract_property(property, text):
        matches = match_between_strings(text, f'{property}="', '"')
        if matches:
            return matches[0]
        return None

    legend_items = []
    # unescape html
    html = frappe.utils.html_utils.unescape_html(sld)
    # get colormap entries : pattern = re.escape('<sld:ColorMapEntry') + r'(.*?)' + re.escape('/>')
    entries = match_between_strings(html, start_str='<sld:ColorMapEntry ', end_str='/>') 
    for entry in entries:
        legend_items.append(frappe._dict({
            'label': _extract_property('label', entry),
            'color': _extract_property('color', entry),
            'expression': _extract_property('quantity', entry),
        }))
    return legend_items