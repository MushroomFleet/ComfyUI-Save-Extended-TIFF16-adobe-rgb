"""
@author: [Your Name / Handle]
@title: Save Image Extended AdobeRGB
@nickname: AdobeRGB Save
@description: Save images with color space control (sRGB / Adobe RGB 1998) and bit depth (8/16-bit). Standalone node — no dependencies on Save Image Extended.
"""

from .adobergb_save_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = None

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
