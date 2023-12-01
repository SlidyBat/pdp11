from binaryninja import *
from .pdparch import PDP11, BSD2
from .pdpview import PDP11View

# Arch
PDP11.register()

# Platform
bsd2 = BSD2(Architecture['pdp11'])
bsd2.register('2.11bsd')

# View
PDP11View.register()