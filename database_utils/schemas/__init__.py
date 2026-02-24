from .client import *
from .company import *
from .custom_field import *
from .invoice import *
from .notification import *
from .order import *
from .order_item import *
from .permission import *
from .product import *
from .recurring_order import *
from .requests import *
from .role import *
from .task import *
from .task_state import *
from .task_template import *
from .user import *
from .workflow import *
from .integration import *

# Rebuild models with forward references to resolve circular dependencies
from .order import OrderOut
from .recurring_order import (
    RecurringOrderOut,
    RecurringOrderCreateResponse,
    OrderGenerationResponse,
    GeneratedOrdersWithGaps,
    RegeneratePeriodResponse,
)

OrderOut.model_rebuild()
RecurringOrderOut.model_rebuild()
RecurringOrderCreateResponse.model_rebuild()
OrderGenerationResponse.model_rebuild()
GeneratedOrdersWithGaps.model_rebuild()
RegeneratePeriodResponse.model_rebuild()