from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

DictKV = Dict[str, Any]
ListDictKV = List[DictKV]


class SideSupport(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class ProjectStatus(str, Enum):
    APPROVED = "approved"
    ARCHIVED = "archived"
    REJECTED = "rejected"
    DRAFT = "draft"
    UNLISTED = "unlisted"
    PROCESSING = "processing"
    WITHHELD = "withheld"
    SCHEDULED = "scheduled"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class RequestedStatus(str, Enum):
    APPROVED = "approved"
    ARCHIVED = "archived"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    DRAFT = "draft"


class ProjectType(str, Enum):
    MOD = "mod"
    MODPACK = "modpack"
    RESOURCEPACK = "resourcepack"


class VersionType(str, Enum):
    RELEASE = "release"
    BETA = "beta"
    ALPHA = "alpha"


class VersionStatus(str, Enum):
    LISTED = "listed"
    ARCHIVED = "archived"
    DRAFT = "draft"
    UNLISTED = "unlisted"
    SCHEDULED = "scheduled"
    UNKNOWN = "unknown"


class RequestedVersionStatus(str, Enum):
    LISTED = "listed"
    ARCHIVED = "archived"
    DRAFT = "draft"
    UNLISTED = "unlisted"


@dataclass
class NewVersion:
    name: str
    version_number: str
    project_id: str
    game_versions: List[str]
    loaders: List[str]
    version_type: VersionType
    featured: bool = True
    changelog: Optional[str] = None
    dependencies: Optional[List[DictKV]] = None
    status: VersionStatus = VersionStatus.LISTED
    requested_status: Optional[RequestedVersionStatus] = None


@dataclass
class DonationUrl:
    id: str
    platform: str
    url: str


@dataclass
class NewProject:
    slug: str
    title: str
    description: str
    categories: List[str]
    client_side: SideSupport
    server_side: SideSupport
    body: str
    project_type: ProjectType
    initial_versions: Optional[List[NewVersion]] = field(default_factory=list)
    additional_categories: Optional[List[str]] = None
    issues_url: Optional[str] = None
    source_url: Optional[str] = None
    organization_id: Optional[str] = None
    wiki_url: Optional[str] = None
    discord_url: Optional[str] = None
    donation_urls: Optional[List[DonationUrl]] = None
    requested_status: Optional[RequestedStatus] = RequestedStatus.UNLISTED
    status: Optional[RequestedStatus] = RequestedStatus.DRAFT
    license_id: Optional[str] = None
    license_url: Optional[str] = None
    is_draft: bool = True


@dataclass
class ProjectUpdate:
    slug: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    client_side: Optional[str] = None
    server_side: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    requested_status: Optional[str] = None
    additional_categories: Optional[List[str]] = None
    issues_url: Optional[str] = None
    source_url: Optional[str] = None
    wiki_url: Optional[str] = None
    discord_url: Optional[str] = None
    donation_urls: Optional[List[Dict[str, Any]]] = None
    license_id: Optional[str] = None
    license_url: Optional[str] = None
    moderation_message: Optional[str] = None
    moderation_message_body: Optional[str] = None


@dataclass
class VersionUpdate:
    name: Optional[str] = None
    version_number: Optional[str] = None
    changelog: Optional[str] = None
    dependencies: Optional[List[DictKV]] = None
    game_versions: Optional[List[str]] = None
    version_type: Optional[VersionType] = None
    loaders: Optional[List[str]] = None
    featured: Optional[bool] = None
    status: Optional[VersionStatus] = None
    requested_status: Optional[RequestedVersionStatus] = None


@dataclass
class GalleryImage:
    image_path: Path
    ext: str
    featured: bool
    title: Optional[str] = None
    description: Optional[str] = None
    ordering: Optional[int] = None
