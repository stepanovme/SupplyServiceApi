from app.models.auth_user import AuthUser
from app.models.chat import Attachment, Chat, ChatMember, ChatReadStatus, Message, MessageMention
from app.models.contract import (
    Contract,
    ContractFile,
    ContractFolder,
    ContractLog,
    ContractObject,
    ContractParty,
    ContractStatus,
    ContractUserRole,
    ContractWorkType,
    DocumentType,
    WorkContract,
)
from app.models.deal import Deal, DealDelivery, DealProduct, DealService
from app.models.delivery import Delivery, DeliveryItem
from app.models.delivery_item_mapping import DeliveryItemMapping
from app.models.item_mapping import ItemMapping
from app.models.invoice import Invoice, InvoiceFile, InvoiceItem, InvoiceLog, InvoicePayment
from app.models.invoice_outgoing import (
    InvoiceOutgoing,
    InvoiceOutgoingItem,
    InvoiceOutgoingNomenclature,
    InvoiceOutgoingUnit,
)
from app.models.invoice_payment_file import InvoicePaymentFile
from app.models.project import Project
from app.models.project_user_role import ProjectUserRole
from app.models.request_file import FileAudit, FileDB, FileType, NomenclatureFile, RequestFile
from app.models.request_supplier import (
    RequestSupplier,
    RequestSupplierLink,
    RequestSupplierEmailSender,
    RequestSupplierFile,
    RequestSupplierItem,
    RequestSupplierRecipient,
)
from app.models.request_specification import RequestSpecification
from app.models.request_warehouse_list import RequestWarehouseList
from app.models.specification import Specification, SpecificationFile
from app.models.reference_object import ContractRef, ObjectLevel, RefObject, WorkTypeRef
from app.models.session import SessionDB
from app.models.smtp import Smtp
from app.models.supply_request import (
    NomenclatureRef,
    RequestItem,
    RequestLog,
    StatusRef,
    SupplyRequest,
    UnitRef,
    WarehouseCategoryRef,
)
from app.models.upd_document import UpdDocument, UpdDocumentItem
from app.models.upd_item_mapping import UpdItemMapping
from app.models.letter import (
    Letter,
    LetterFile,
    LetterFolder,
    LetterObject,
    LetterStatus,
    LetterUserRole,
)
from app.models.warehouse import Warehouse, WarehouseList
from app.models.warehouse_receipt import (
    WarehouseFile,
    WarehouseReceipt,
    WarehouseReceiptItem,
    WarehouseReceiptItemLog,
    WarehouseReceiptLog,
)
from app.models.wiki import WikiPage
from app.models.wiki_file import WikiFile
from app.models.news import NewsPost
from app.models.one_c import OneCOrganization, OneCProfile
from app.models.act import Act, ActFile, ActFolder, ActStatus, ActType, ActUserRole
from app.models.project_user_role_template import ProjectUserRoleTemplate
from app.models.invoice_user import InvoiceUser
from app.models.object_setting import ObjectSetting
from app.models.object_settings_template import ObjectSettingsTemplate
from app.models.push_subscription import PushSubscription
from app.models.saved_filter import SavedFilter
from app.models.extract import Extract, ExtractFile, ExtractItem, ExtractItemPayment
from app.models.notification_feed import NotificationFeed
from app.models.documents_list import DocumentsList
from app.models.buh import BuhAccess, BuhFile, BuhFolder
from app.models.document_access_setting import DocumentAccessSetting
